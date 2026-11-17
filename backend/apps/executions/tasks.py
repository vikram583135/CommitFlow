"""Claim executions atomically and preserve proposals across publication retries."""
import difflib
import hashlib
import hmac
import json
import logging
from datetime import timedelta
from zoneinfo import ZoneInfo
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.authentication.models import User
from apps.automations.models import Automation
from apps.executions.models import Execution, GeneratedFile, PublishedChange, GenerationUsage
from apps.ai_engine.models import AIProviderConfig
from apps.ai_engine.adapters import get_ai_adapter, CodeProposal
from apps.validation.validator import ValidationEngine
from apps.git_publishing.publisher import GitPublishingService
from apps.github_integration.services import GitHubAppService, GitHubAPIError
logger = logging.getLogger(__name__)


def set_execution_step(execution, step, message=''):
    execution.validation_results = {**(execution.validation_results or {}), 'current_step': step, 'step_message': message}
    execution.heartbeat_at = timezone.now()
    execution.save(update_fields=['validation_results', 'heartbeat_at'])


def configuration(automation):
    repo = automation.repository
    return dict(repository_id=str(repo.pk), connection_id=str(repo.connection_id), full_name=repo.full_name,
                default_branch=repo.default_branch, allowed_paths=repo.allowed_paths, max_files=automation.max_files,
                branch_strategy=automation.branch_strategy, require_approval=automation.require_approval,
                instructions=automation.instructions, task_type=automation.task_type,
                sandbox_required=settings.ENABLE_PYTHON_SANDBOX,
                ai_config_id=str(automation.ai_config_id) if automation.ai_config_id else None)


def snapshot_digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def mark_finished(execution, state, message):
    execution.status = state
    execution.error_message = message if state != 'SUCCESS' else ''
    execution.completed_at = timezone.now()
    set_execution_step(execution, state, message)
    execution.save(update_fields=['status', 'error_message', 'completed_at'])


def enqueue_execution(execution):
    try:
        execute_automation_task.delay(str(execution.automation_id), execution.scheduled_slot)
    except Exception:
        logger.error('Queue handoff failed for execution %s', execution.pk)
        Execution.objects.filter(pk=execution.pk, status='PENDING').update(
            status='FAILED', completed_at=timezone.now(), error_message='Queue unavailable. Retry when the worker is connected.')
        return False
    return True


def assert_authorized(automation):
    repo = automation.repository
    if (not automation.enabled or not automation.user.is_active or not repo.is_active or not repo.connection.is_active
            or repo.connection.user_id != automation.user_id
            or (automation.ai_config_id and (automation.ai_config.user_id != automation.user_id or not automation.ai_config.is_active))):
        raise ValueError('Automation is disabled or its repository/AI authorization is no longer valid.')


def publish_snapshot(execution):
    automation = Automation.objects.select_related('repository__connection', 'ai_config', 'user').get(pk=execution.automation_id)
    assert_authorized(automation)
    snapshot = execution.snapshot
    if (not snapshot or not hmac.compare_digest(snapshot_digest(snapshot), execution.proposal_hash)
            or snapshot['configuration'] != configuration(automation)):
        raise ValueError('Proposal or automation policy changed. Run again to generate a new proposal.')
    proposal = CodeProposal(**snapshot['proposal'])
    if settings.ENABLE_PYTHON_SANDBOX and not snapshot.get('sandbox', {}).get('passed'):
        raise ValueError('This proposal has no successful sandbox result.')
    files = sorted((f.file_path, f.change_type, f.new_content) for f in execution.generated_files.all())
    expected = sorted((f.path, f.change_type, f.content) for f in proposal.files)
    if files != expected:
        raise ValueError('Proposal files changed. Generate a new proposal.')
    validation = ValidationEngine.validate(proposal, automation.repository.allowed_paths, automation.max_files,
                                           snapshot['originals'])
    if not validation.is_valid:
        raise ValueError('Proposal no longer passes validation. Generate a new proposal.')
    if (automation.require_approval or automation.branch_strategy == 'DIRECT_PUSH') and not execution.approved_at:
        raise ValueError('Manual approval is required.')
    set_execution_step(execution, 'PUBLISHING_PULL_REQUEST', 'Publishing the reviewed proposal to GitHub...')
    result = GitPublishingService.publish(automation.repository, proposal, automation.branch_strategy,
        execution_id=str(execution.pk), base_sha=snapshot['base_sha'], base_tree_sha=snapshot['base_tree_sha'],
        file_modes=snapshot['file_modes'], commit_date=execution.started_at.isoformat())
    if not result.success:
        raise GitHubAPIError(result.error or 'GitHub publication failed.', result.retryable)
    with transaction.atomic():
        locked = Execution.objects.select_for_update().get(pk=execution.pk)
        PublishedChange.objects.update_or_create(execution=locked, defaults=dict(
            branch_name=result.branch_name, commit_sha=result.commit_sha, commit_message=proposal.commit_message,
            pull_request_url=result.pull_request_url, pull_request_number=result.pull_request_number))
        mark_finished(locked, 'SUCCESS', 'GitHub confirmed publication.')
        Automation.objects.filter(pk=automation.pk).update(last_run_at=timezone.now())
    return f'Execution {execution.pk} published successfully: {result.commit_sha}'


@shared_task(bind=True, max_retries=3)
def execute_automation_task(self, automation_id, scheduled_slot):
    try:
        automation = Automation.objects.select_related('repository__connection', 'ai_config', 'user').get(pk=automation_id)
    except Automation.DoesNotExist:
        return 'Automation not found.'
    execution, _ = Execution.objects.get_or_create(automation=automation, scheduled_slot=scheduled_slot,
        defaults={'status': 'PENDING', 'idempotency_key': f'{automation_id}:{scheduled_slot}'})
    with transaction.atomic():
        User.objects.select_for_update().get(pk=automation.user_id)
        state = 'PUBLISHING' if execution.snapshot else 'RUNNING'
        if not Execution.objects.filter(pk=execution.pk, status='PENDING').update(
                status=state, completed_at=None, error_message='', heartbeat_at=timezone.now()):
            return f'Execution {execution.pk} already claimed or completed.'
        execution.refresh_from_db()
    try:
        assert_authorized(automation)
        if execution.snapshot:
            return publish_snapshot(execution)
        ai_config = automation.ai_config or AIProviderConfig.objects.filter(user=automation.user, is_active=True).first()
        if not ai_config or not ai_config.get_api_key():
            mark_finished(execution, 'REJECTED', 'AI Provider not configured. Save an active AI provider key first.')
            return execution.error_message
        initial_configuration = configuration(automation)
        set_execution_step(execution, 'FETCHING_CONTEXT', 'Reading repository files at a fixed commit...')
        context = GitHubAppService.fetch_repository_context(automation.repository)
        context['recent_commits'] = list(PublishedChange.objects.filter(execution__automation=automation)
                                        .order_by('-published_at').values_list('commit_message', flat=True)[:5])
        context['max_files'] = automation.max_files
        with transaction.atomic():
            User.objects.select_for_update().get(pk=automation.user_id)
            if GenerationUsage.objects.filter(user=automation.user, created_at__gte=timezone.now()-timedelta(days=1)).count() >= settings.MAX_DAILY_EXECUTIONS:
                mark_finished(execution, 'REJECTED', 'Daily generation limit reached. Try again tomorrow.')
                return execution.error_message
            GenerationUsage.objects.create(user=automation.user, execution=execution)
        set_execution_step(execution, 'GENERATING_CHANGES', 'Generating a proposal from the supplied source files...')
        adapter = get_ai_adapter(ai_config)
        proposal = adapter.generate_changes(automation.instructions, context)
        usage = getattr(adapter, 'usage', {})
        if isinstance(usage, dict):
            execution.input_tokens = usage.get('input_tokens', 0)
            execution.output_tokens = usage.get('output_tokens', 0)
            execution.save(update_fields=['input_tokens', 'output_tokens'])
        set_execution_step(execution, 'VALIDATING_SAFETY', 'Checking paths, secrets, syntax, and substantive changes...')
        originals = {f.path: context['source_files'].get(f.path) for f in proposal.files}
        validation = ValidationEngine.validate(proposal, automation.repository.allowed_paths, automation.max_files, originals)
        for file in proposal.files:
            entry = context['entries'].get(file.path)
            if entry and (file.path not in context['source_files'] or entry.get('mode') not in ('100644', '100755')):
                validation.errors.append(f'{file.path} exists but was not supplied as editable source.')
                validation.checks['changes'] = False
            parts = file.path.split('/')
            if any(context['entries'].get('/'.join(parts[:index]), {}).get('type') not in (None, 'tree')
                   for index in range(1, len(parts))):
                validation.errors.append(f'{file.path} would replace an existing file or symlink ancestor.')
                validation.checks['changes'] = False
        validation.is_valid = not validation.errors
        execution.validation_results = validation.to_dict()
        if not validation.is_valid:
            mark_finished(execution, 'REJECTED', '\n'.join(validation.errors))
            return execution.error_message
        if settings.ENABLE_PYTHON_SANDBOX:
            from apps.validation.sandbox import run_python_tests
            sandbox = run_python_tests({**context['source_files'], **{file.path: file.content for file in proposal.files}})
            execution.validation_results['sandbox'] = sandbox
            execution.validation_results['checks']['tests'] = sandbox['passed']
            if not sandbox['passed']:
                execution.validation_results['is_valid'] = False
                mark_finished(execution, 'REJECTED', sandbox['message'])
                return execution.error_message
        automation.refresh_from_db()
        # Re-read related objects as well; generation may have taken minutes.
        automation = Automation.objects.select_related('repository__connection', 'ai_config', 'user').get(pk=automation.pk)
        assert_authorized(automation)
        if configuration(automation) != initial_configuration:
            raise ValueError('Automation changed during generation. Run again.')
        snapshot = dict(configuration=initial_configuration, proposal=proposal.model_dump(),
                        sandbox=execution.validation_results.get('sandbox', {}),
                        base_sha=context['base_sha'], base_tree_sha=context['base_tree_sha'], originals=originals,
                        file_modes={f.path: context['entries'].get(f.path, {}).get('mode', '100644') for f in proposal.files})
        with transaction.atomic():
            execution.generated_files.all().delete()
            for file in proposal.files:
                original = originals[file.path] or ''
                diff = ''.join(difflib.unified_diff(original.splitlines(keepends=True), file.content.splitlines(keepends=True),
                                                   fromfile='a/'+file.path, tofile='b/'+file.path))
                GeneratedFile.objects.create(execution=execution, file_path=file.path, change_type=file.change_type,
                                             original_content=original, new_content=file.content, diff_patch=diff)
            execution.snapshot = snapshot
            execution.proposal_hash = snapshot_digest(snapshot)
            execution.status = 'AWAITING_APPROVAL' if automation.require_approval else 'PUBLISHING'
            set_execution_step(execution, execution.status, 'Proposal ready for review.' if automation.require_approval else 'Publishing validated changes...')
            execution.save(update_fields=['snapshot', 'proposal_hash', 'status'])
        if execution.status == 'AWAITING_APPROVAL':
            return f'Execution {execution.pk} awaiting manual user approval.'
        return publish_snapshot(execution)
    except Exception as exc:
        logger.warning('Execution %s failed with %s', execution.pk, exc.__class__.__name__)
        retryable = (isinstance(exc, GitHubAPIError) and exc.retryable) or exc.__class__.__name__ in {
            'RateLimitError', 'APITimeoutError', 'APIConnectionError', 'InternalServerError'}
        if retryable and self.request.retries < self.max_retries:
            execution.status = 'PENDING'
            execution.attempt_number += 1
            set_execution_step(execution, 'RETRYING', 'Temporary provider failure. Retrying shortly...')
            execution.save(update_fields=['status', 'attempt_number'])
            raise self.retry(countdown=min(30 * 2**self.request.retries, 240))
        if isinstance(exc, (ValueError, GitHubAPIError)):
            message = str(exc) if isinstance(exc, GitHubAPIError) else 'Proposal or configuration is invalid. Review settings and generate again.'
        elif isinstance(exc, SoftTimeLimitExceeded):
            message = 'Execution timed out. Retry to reconcile any existing publication.'
        else:
            message = 'Execution failed. Check provider credentials and service availability, then retry.'
        mark_finished(execution, 'FAILED', message)
        return message


@shared_task
def dispatch_scheduled_automation(automation_id):
    from apps.automations.scheduling import sync_schedule
    with transaction.atomic():
        automation = Automation.objects.select_for_update().filter(pk=automation_id, enabled=True).first()
        if not automation:
            return
        due = automation.next_run_at
        now = timezone.now()
        if due is None:
            sync_schedule(automation)
            return
        if due > now:
            return
        sync_schedule(automation)
        # Do not backfill contributions after an extended outage.
        if due < now - timedelta(minutes=5):
            return
        slot = 'scheduled:' + due.astimezone(ZoneInfo(automation.timezone)).strftime('%Y-%m-%d-%H-%M')
        execution, created = Execution.objects.get_or_create(automation=automation, scheduled_slot=slot,
            defaults={'idempotency_key': f'{automation.pk}:{slot}'})
    if created:
        enqueue_execution(execution)


@shared_task
def recover_interrupted_executions():
    # Longer than the worker's hard time limit; never regenerate a staged publication.
    Execution.objects.filter(status__in=['RUNNING', 'PUBLISHING'],
        heartbeat_at__lt=timezone.now()-timedelta(minutes=15)).update(status='FAILED', completed_at=timezone.now(),
        error_message='Worker interrupted. Retry to reconcile the original execution.')
    # Recover queue handoff failures without changing proposal identity.
    for execution in Execution.objects.filter(status='PENDING', started_at__lt=timezone.now()-timedelta(minutes=15))[:100]:
        enqueue_execution(execution)
