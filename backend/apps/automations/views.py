import uuid
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from .models import Automation
from .serializers import AutomationSerializer
from apps.executions.models import Execution
from apps.executions.serializers import ExecutionSerializer
from apps.executions.tasks import enqueue_execution


class AutomationListCreateView(generics.ListCreateAPIView):
    serializer_class = AutomationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Automation.objects.filter(user=self.request.user).select_related('repository__connection', 'ai_config')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AutomationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AutomationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Automation.objects.filter(user=self.request.user).select_related('repository__connection', 'ai_config')


class AutomationRunTriggerView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'run'

    def post(self, request, pk=None):
        try:
            key = str(uuid.UUID(request.headers.get('Idempotency-Key', str(uuid.uuid4()))))
        except (ValueError, TypeError):
            return Response({'error': 'Idempotency-Key must be a UUID.'}, status=400)
        with transaction.atomic():
            automation = get_object_or_404(Automation.objects.select_for_update(), pk=pk, user=request.user)
            if not automation.enabled:
                return Response({'error': 'Enable this automation before running it.'}, status=409)
            slot = 'manual:' + key
            execution = Execution.objects.filter(automation=automation, scheduled_slot=slot).first()
            if execution:
                return Response(ExecutionSerializer(execution).data, status=200)
            if automation.executions.filter(status__in=['PENDING', 'RUNNING', 'PUBLISHING']).exists():
                return Response({'error': 'This automation already has a queued or running execution.'}, status=409)
            execution = Execution.objects.create(automation=automation, scheduled_slot=slot,
                                                idempotency_key=f'{automation.pk}:{slot}')
        queued = enqueue_execution(execution)
        execution.refresh_from_db()
        return Response(ExecutionSerializer(execution).data, status=202 if queued else 503)
