import datetime
from celery import shared_task
from django.utils import timezone
from apps.automations.models import Automation
from apps.executions.models import Execution, GeneratedFile, PublishedChange
from apps.ai_engine.models import AIProviderConfig
from apps.ai_engine.adapters import get_ai_adapter, CodeProposal, ProposedFile
from apps.validation.validator import ValidationEngine
from apps.git_publishing.publisher import GitPublishingService
from apps.github_integration.services import GitHubAppService

def set_execution_step(execution: Execution, step_name: str, message: str = ""):
    val = execution.validation_results or {}
    val['current_step'] = step_name
    val['step_message'] = message
    execution.validation_results = val
    execution.save(update_fields=['validation_results'])

@shared_task(bind=True, max_retries=3)
def execute_automation_task(self, automation_id: str, scheduled_slot: str):
    """
    Production Celery task:
    1. Acquires scoped GitHub installation token
    2. Ingests live repository file tree & README
    3. Fetches execution history for anti-duplication memory
    4. Invokes live AI provider with structured JSON schema
    5. Runs security validation sandbox
    6. Publishes real commits and Pull Request via GitHub API
    """
    try:
        automation = Automation.objects.select_related(
            'repository', 'ai_config', 'repository__connection', 'user'
        ).get(id=automation_id, enabled=True)
    except Automation.DoesNotExist:
        return f"Automation {automation_id} not found or disabled."

    execution, created = Execution.objects.get_or_create(
        automation=automation,
        scheduled_slot=scheduled_slot,
        defaults={
            "status": "RUNNING",
            "idempotency_key": f"{automation_id}:{scheduled_slot}",
            "started_at": timezone.now(),
            "validation_results": {"current_step": "STARTING", "step_message": "Initializing task execution..."}
        }
    )

    if not created and execution.status in ["SUCCESS", "AWAITING_APPROVAL"]:
        return f"Slot {scheduled_slot} already completed."

    execution.status = "RUNNING"
    execution.save(update_fields=['status'])

    try:
        # Step 1: Token Acquisition & Context Gathering
        set_execution_step(execution, "FETCHING_CONTEXT", f"Ingesting repository tree for {automation.repository.full_name}...")
        repo_context = GitHubAppService.fetch_repository_context(automation.repository)

        # Anti-Duplication History: Get recent topics
        recent_commits = PublishedChange.objects.filter(
            execution__automation=automation
        ).order_by('-published_at')[:5].values_list('commit_message', flat=True)
        repo_context['recent_commits'] = list(recent_commits)

        # Step 2: AI Code Generation
        set_execution_step(execution, "GENERATING_CHANGES", "Prompting AI provider with repo context and task rules...")
        
        # Resolve active AI config
        ai_config = automation.ai_config
        if not ai_config:
            ai_config = AIProviderConfig.objects.filter(user=automation.user, is_active=True).first()

        proposal: CodeProposal = None

        if ai_config and ai_config.get_api_key():
            adapter = get_ai_adapter(ai_config)
            proposal = adapter.generate_changes(automation.instructions, repo_context)
        else:
            # If no live AI key is configured, reject run with clear guidance
            execution.status = "REJECTED"
            execution.error_message = (
                "AI Provider not configured. Please open AI Config in the dashboard "
                "and configure an API key (OpenAI, Anthropic, or Gemini) to run automated habits."
            )
            execution.completed_at = timezone.now()
            set_execution_step(execution, "FAILED", execution.error_message)
            execution.save()
            return execution.error_message

        # Step 3: Record Proposed Files
        execution.generated_files.all().delete()
        for f in proposal.files:
            GeneratedFile.objects.create(
                execution=execution,
                file_path=f.path,
                change_type=f.change_type,
                new_content=f.content,
                diff_patch=f"+++ b/{f.path}\n+ {f.content[:200]}..."
            )

        # Step 4: Security & Safety Validation Sandbox
        set_execution_step(execution, "VALIDATING_SAFETY", "Executing path bounds, blacklist, and secret leakage scan...")
        validation = ValidationEngine.validate(proposal, automation.repository.allowed_paths)
        res_dict = validation.to_dict()
        res_dict['current_step'] = "VALIDATING_SAFETY"
        execution.validation_results = res_dict

        if not validation.is_valid:
            execution.status = "REJECTED"
            execution.error_message = "\n".join(validation.errors)
            execution.completed_at = timezone.now()
            set_execution_step(execution, "REJECTED", f"Validation rejected: {execution.error_message}")
            execution.save()
            return f"Validation rejected: {execution.error_message}"

        # Step 5: Check Approval Policy
        if automation.require_approval:
            execution.status = "AWAITING_APPROVAL"
            set_execution_step(execution, "AWAITING_APPROVAL", "Changes staged and ready for user approval.")
            execution.save()
            return f"Execution {execution.id} awaiting manual user approval."

        # Step 6: Git Publishing (Branch + Tree + Commit + PR)
        set_execution_step(execution, "PUBLISHING_PULL_REQUEST", "Publishing feature branch and opening Pull Request on GitHub...")
        pub_result = GitPublishingService.publish(
            repository=automation.repository,
            proposal=proposal,
            branch_strategy=automation.branch_strategy
        )

        if not pub_result.success:
            execution.status = "FAILED"
            execution.error_message = pub_result.error or "Git publish operation failed"
            execution.completed_at = timezone.now()
            set_execution_step(execution, "FAILED", execution.error_message)
            execution.save()
            return f"Git publish failed: {execution.error_message}"

        # Step 7: Record Published Change
        PublishedChange.objects.create(
            execution=execution,
            branch_name=pub_result.branch_name,
            commit_sha=pub_result.commit_sha,
            commit_message=proposal.commit_message,
            pull_request_url=pub_result.pull_request_url,
            pull_request_number=pub_result.pull_request_number
        )

        execution.status = "SUCCESS"
        execution.completed_at = timezone.now()
        set_execution_step(execution, "SUCCESS", f"Published Pull Request #{pub_result.pull_request_number or 'created'}")
        execution.save()

        automation.last_run_at = timezone.now()
        automation.save(update_fields=['last_run_at'])

        return f"Execution {execution.id} published successfully: {pub_result.commit_sha}"

    except Exception as exc:
        execution.status = "FAILED"
        execution.error_message = str(exc)
        execution.completed_at = timezone.now()
        set_execution_step(execution, "FAILED", str(exc))
        execution.save()
        raise exc
