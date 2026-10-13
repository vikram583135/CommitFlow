from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Execution
from .serializers import ExecutionSerializer

class ExecutionListView(generics.ListAPIView):
    serializer_class = ExecutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Execution.objects.filter(automation__user=self.request.user)
        automation_id = self.request.query_params.get('automation_id')
        if automation_id:
            qs = qs.filter(automation_id=automation_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

class ExecutionDetailView(generics.RetrieveAPIView):
    serializer_class = ExecutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Execution.objects.filter(automation__user=self.request.user)

class ExecutionApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        try:
            execution = Execution.objects.get(pk=pk, automation__user=request.user)
            if execution.status != 'AWAITING_APPROVAL':
                return Response(
                    {"error": f"Cannot approve execution in '{execution.status}' status."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            from apps.git_publishing.publisher import GitPublishingService
            from apps.executions.models import PublishedChange
            from apps.ai_engine.adapters.schemas import CodeProposal, ProposedFile
            from django.utils import timezone

            # Reconstruct proposal from stored files
            files = [
                ProposedFile(path=gf.file_path, change_type=gf.change_type, content=gf.new_content)
                for gf in execution.generated_files.all()
            ]
            proposal = CodeProposal(
                summary="User approved commit",
                commit_message=f"feat(auto): approved automated contribution",
                pr_title=f"Habit Contribution [{execution.scheduled_slot}]",
                pr_body="Automated contribution reviewed and approved by user.",
                files=files
            )

            pub_result = GitPublishingService.publish(
                repository=execution.automation.repository,
                proposal=proposal,
                branch_strategy=execution.automation.branch_strategy
            )

            if not pub_result.success:
                execution.status = 'FAILED'
                execution.error_message = pub_result.error or 'Failed to publish to GitHub'
                execution.save()
                return Response({"error": execution.error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            PublishedChange.objects.create(
                execution=execution,
                branch_name=pub_result.branch_name,
                commit_sha=pub_result.commit_sha,
                commit_message=proposal.commit_message,
                pull_request_url=pub_result.pull_request_url,
                pull_request_number=pub_result.pull_request_number
            )
            execution.status = 'SUCCESS'
            execution.completed_at = timezone.now()
            execution.save()

            return Response(ExecutionSerializer(execution).data)

        except Execution.DoesNotExist:
            return Response({"error": "Execution not found"}, status=status.HTTP_404_NOT_FOUND)

class ExecutionRetryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk=None):
        try:
            execution = Execution.objects.get(pk=pk, automation__user=request.user)
            from apps.executions.tasks import execute_automation_task
            import datetime

            new_slot = f"{execution.scheduled_slot}-retry-{int(datetime.datetime.now().timestamp())}"
            task = execute_automation_task.delay(str(execution.automation.id), new_slot)
            return Response({
                "message": "Retry queued",
                "task_id": task.id,
                "new_slot": new_slot
            })
        except Execution.DoesNotExist:
            return Response({"error": "Execution not found"}, status=status.HTTP_404_NOT_FOUND)
