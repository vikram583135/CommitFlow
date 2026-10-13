from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Automation
from .serializers import AutomationSerializer

class AutomationListCreateView(generics.ListCreateAPIView):
    serializer_class = AutomationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Automation.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class AutomationDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AutomationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Automation.objects.filter(user=self.request.user)

class AutomationRunTriggerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        try:
            automation = Automation.objects.get(pk=pk, user=request.user)
            from apps.executions.tasks import execute_automation_task
            import datetime

            slot = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
            # Dispatch to Celery worker (or run directly if configured)
            task = execute_automation_task.delay(str(automation.id), slot)
            return Response({
                "message": "Automation execution queued",
                "task_id": task.id,
                "slot": slot
            }, status=status.HTTP_202_ACCEPTED)
        except Automation.DoesNotExist:
            return Response({"error": "Automation not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
