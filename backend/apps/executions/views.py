import json
import time
from datetime import timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.db import transaction
from django.db.models.functions import TruncDate
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from .models import Execution, PublishedChange
from .serializers import ExecutionSerializer, ExecutionSummarySerializer
from .tasks import enqueue_execution, configuration, snapshot_digest


class ExecutionListView(generics.ListAPIView):
    serializer_class = ExecutionSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Execution.objects.filter(automation__user=self.request.user).select_related('automation__repository', 'published_change')
        automation_id = self.request.query_params.get('automation_id')
        if automation_id:
            from django.core.exceptions import ValidationError
            try:
                qs = qs.filter(automation_id=automation_id)
            except (ValueError, ValidationError):
                return qs.none()
        if self.request.query_params.get('status'):
            qs = qs.filter(status=self.request.query_params['status'])
        return qs


class ExecutionDetailView(generics.RetrieveAPIView):
    serializer_class = ExecutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Execution.objects.filter(automation__user=self.request.user).select_related(
            'automation__repository', 'published_change').prefetch_related('generated_files')


class ExecutionMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            zone = ZoneInfo(request.query_params.get('timezone', 'UTC'))
        except (ZoneInfoNotFoundError, ValueError):
            return Response({'error': 'Invalid timezone.'}, status=400)
        runs = Execution.objects.filter(automation__user=request.user)
        days = set(runs.filter(status='SUCCESS').annotate(day=TruncDate('completed_at', tzinfo=zone)).values_list('day', flat=True))
        today = timezone.now().astimezone(zone).date()
        day = today if today in days else today - timedelta(days=1)
        streak = 0
        while day in days:
            streak += 1
            day -= timedelta(days=1)
        checked = runs.filter(validation_results__has_key='is_valid')
        checked_count = checked.count()
        return Response(dict(streak_days=streak, active_automations=request.user.automations.filter(enabled=True).count(),
            total_prs=PublishedChange.objects.filter(execution__automation__user=request.user, pull_request_url__isnull=False).count(),
            validation_pass_rate=round(100 * checked.filter(validation_results__is_valid=True).count()/checked_count) if checked_count else None))


class ExecutionStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        execution = get_object_or_404(Execution, pk=pk, automation__user=request.user)

        def event_stream():
            previous = None
            for _ in range(60):
                execution.refresh_from_db()
                payload = dict(id=str(execution.pk), status=execution.status,
                               step=execution.validation_results.get('current_step', ''),
                               message=execution.validation_results.get('step_message', ''), error=execution.error_message)
                encoded = json.dumps(payload)
                if encoded != previous:
                    yield f'data: {encoded}\n\n'
                    previous = encoded
                else:
                    yield ': heartbeat\n\n'
                if execution.status in ('SUCCESS', 'FAILED', 'REJECTED', 'CANCELLED', 'AWAITING_APPROVAL'):
                    break
                time.sleep(1)
        response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ExecutionApproveView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'run'

    def post(self, request, pk=None):
        if not isinstance(request.data, dict):
            return Response({'error': 'A JSON object is required.'}, status=400)
        with transaction.atomic():
            execution = get_object_or_404(Execution.objects.select_for_update(of=('self',)), pk=pk, automation__user=request.user)
            if execution.status != 'AWAITING_APPROVAL':
                return Response({'error': 'This execution is not awaiting approval.'}, status=409)
            if (not execution.snapshot or request.data.get('proposal_hash') != execution.proposal_hash
                    or snapshot_digest(execution.snapshot) != execution.proposal_hash
                    or execution.snapshot.get('configuration') != configuration(execution.automation)):
                return Response({'error': 'Proposal or policy changed. Generate a new proposal.'}, status=409)
            execution.approved_at = timezone.now()
            execution.status = 'PENDING'
            execution.save(update_fields=['approved_at', 'status'])
        queued = enqueue_execution(execution)
        execution.refresh_from_db()
        return Response(ExecutionSerializer(execution).data, status=202 if queued else 503)


class ExecutionRetryView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'run'

    def post(self, request, pk=None):
        with transaction.atomic():
            execution = get_object_or_404(Execution.objects.select_for_update(of=('self',)), pk=pk, automation__user=request.user)
            if execution.status != 'FAILED' or execution.attempt_number >= 8:
                return Response({'error': 'Only failed executions with fewer than eight attempts can be retried.'}, status=409)
            if not execution.automation.enabled:
                return Response({'error': 'Enable the automation before retrying.'}, status=409)
            execution.status = 'PENDING'
            execution.error_message = ''
            execution.completed_at = None
            execution.attempt_number += 1
            execution.save(update_fields=['status', 'error_message', 'completed_at', 'attempt_number'])
        queued = enqueue_execution(execution)
        execution.refresh_from_db()
        return Response(ExecutionSerializer(execution).data, status=202 if queued else 503)
