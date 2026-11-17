"""Security, scheduling, proposal lifecycle, and GitHub failure regression tests."""
import base64
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs
import httpx
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from django_celery_beat.models import PeriodicTask
from apps.authentication.models import User, OAuthAttempt, SocialIdentity
from apps.authentication.oauth import OAuthService
from apps.common.encryption import encrypt_secret, decrypt_secret, mask_secret
from apps.github_integration.models import GitHubConnection, Repository
from apps.github_integration.services import GitHubAppService, GitHubAPIError
from apps.ai_engine.models import AIProviderConfig
from apps.ai_engine.adapters.schemas import CodeProposal, ProposedFile
from apps.validation.validator import ValidationEngine
from apps.automations.models import Automation
from apps.executions.models import Execution, PublishedChange
from apps.executions.tasks import execute_automation_task, dispatch_scheduled_automation, recover_interrupted_executions
from apps.git_publishing.publisher import GitPublishingService


def proposal(path='src/example.py', content='def example(value):\n    return value + 1\n', kind='CREATE'):
    return CodeProposal(summary='Add example', commit_message='feat: add example', pr_title='Add example',
                        pr_body='Adds a useful example.', files=[ProposedFile(path=path, content=content, change_type=kind)])


class ValidationTests(SimpleTestCase):
    def test_encryption(self):
        secret='test-credential-value'
        self.assertEqual(decrypt_secret(encrypt_secret(secret)), secret)
        self.assertNotIn(secret, mask_secret(secret))

    def test_unsafe_paths_and_boundaries(self):
        for path in ['../secret.py', '..', '/src/test.py', 'src/../test.py', 'src//test.py',
                     'src\\test.py', 'C:/src/test.py', 'src-private/test.py', './src/test.py',
                     'src/.env.production', 'src/Dockerfile', 'src/id_rsa', 'src/.github/workflows/a.py',
                     'src/key.pem', 'src/key.key']:
            with self.subTest(path=path):
                self.assertFalse(ValidationEngine.validate(proposal(path), ['src/']).is_valid)

    def test_empty_boundaries_fail_closed(self):
        self.assertFalse(ValidationEngine.validate(proposal(), []).is_valid)

    def test_secrets(self):
        for secret in ['sk-proj-'+ 'x'*40, 'sk-ant-api03-'+ 'a'*40, 'ghp_'+'x'*36,
                       'github_pat_'+'x'*82, '-----BEGIN PRIVATE KEY-----', 'AKIA'+'A'*16]:
            with self.subTest(secret=secret[:15]):
                self.assertFalse(ValidationEngine.validate(proposal(content='VALUE = '+repr(secret)), ['src/']).is_valid)

    def test_metadata_secrets(self):
        value=proposal();value.pr_body='ghp_'+'x'*36
        self.assertFalse(ValidationEngine.validate(value, ['src/']).is_valid)

    def test_duplicate_files_and_limits(self):
        value=proposal();value.files*=2
        self.assertFalse(ValidationEngine.validate(value,['src/']).is_valid)
        self.assertFalse(ValidationEngine.validate(value,['src/'],max_files=1).is_valid)

    def test_meaningless_or_invalid_code(self):
        for content in ['# '+ 'comment '*20, 'def broken(:\n    return 1000000', ' \n\t ']:
            with self.subTest(content=content):
                self.assertFalse(ValidationEngine.validate(proposal(content=content),['src/']).is_valid)

    def test_existing_file_semantics(self):
        value=proposal()
        self.assertFalse(ValidationEngine.validate(value,['src/'],originals={value.files[0].path:'old content'}).is_valid)
        value.files[0].change_type='MODIFY'
        self.assertFalse(ValidationEngine.validate(value,['src/'],originals={}).is_valid)
        self.assertFalse(ValidationEngine.validate(value,['src/'],originals={value.files[0].path:value.files[0].content}).is_valid)

    def test_valid_proposal_reports_static_limits(self):
        result=ValidationEngine.validate(proposal(),['src/'],originals={})
        self.assertTrue(result.is_valid, result.errors)
        self.assertTrue(result.warnings)
        self.assertEqual(len(result.checks),4)


class Fixtures(TestCase):
    def setUp(self):
        cache.clear()
        self.user=User.objects.create_user(email='owner@example.com',password='StrongTestPassword!936',email_verified=True)
        self.other=User.objects.create_user(email='other@example.com',password='StrongTestPassword!936',email_verified=True)
        self.client=APIClient();self.client.force_authenticate(self.user)
        self.connection=GitHubConnection.objects.create(user=self.user,github_user_id='42',github_username='owner',installation_id='oauth_user_account')
        self.connection.set_access_token('fake-oauth-token');self.connection.save()
        self.repo=Repository.objects.create(connection=self.connection,github_repo_id='99',full_name='owner/repo',allowed_paths=['src/','tests/'])
        self.config=AIProviderConfig.objects.create(user=self.user,provider='openai',model_name='gpt-4o-mini')
        self.config.set_api_key('fake-ai-key');self.config.save()
        self.auto=Automation.objects.create(user=self.user,repository=self.repo,ai_config=self.config,title='Daily practice',instructions='Add useful code')
        self.context=dict(base_sha='BASE_COMMIT',base_tree_sha='BASE_TREE',source_files={},entries={},file_tree=[],allowed_paths=['src/'])

    def generate(self, slot='test-slot', value=None):
        with patch('apps.executions.tasks.GitHubAppService.fetch_repository_context',return_value=self.context), \
             patch('apps.executions.tasks.get_ai_adapter') as adapter:
            adapter.return_value.generate_changes.return_value=value or proposal()
            execute_automation_task(str(self.auto.pk),slot)
        return Execution.objects.get(automation=self.auto,scheduled_slot=slot)

    def data(self,**values):
        return dict(title='Another rule',instructions='Add useful code',repository=str(self.repo.pk),**values)


class AuthTests(Fixtures):
    def setUp(self):
        super().setUp();self.client=APIClient()

    def begin(self,provider='github',authenticated=False):
        self.verifier='a'*64
        challenge=base64.urlsafe_b64encode(hashlib.sha256(self.verifier.encode()).digest()).rstrip(b'=').decode()
        if authenticated:self.client.force_authenticate(self.user)
        with override_settings(GITHUB_CLIENT_ID='configured',GITHUB_CLIENT_SECRET='configured',GOOGLE_CLIENT_ID='configured',GOOGLE_CLIENT_SECRET='configured'):
            response=self.client.get('/api/auth/oauth/url/',dict(provider=provider,redirect_uri='http://localhost:3000/auth/callback',code_challenge=challenge))
        self.assertEqual(response.status_code,200,response.data)
        return dict(provider=provider,state=response.data['state'],code='test-code',code_verifier=self.verifier,redirect_uri='http://localhost:3000/auth/callback')

    def profile(self,email='new@example.com',subject='88'):
        return dict(provider_id=subject,email=email,name='New User',login='newuser',access_token='fake-token')

    @override_settings(GITHUB_CLIENT_ID='',GITHUB_CLIENT_SECRET='')
    def test_missing_oauth_credentials_fail_closed(self):
        with self.assertRaises(ValueError):OAuthService.exchange('github','','http://localhost:3000/auth/callback','a'*64)
        response=self.client.post('/api/auth/oauth/callback/',{'provider':'github','code':''})
        self.assertEqual(response.status_code,400)
        self.assertFalse(User.objects.filter(email='developer@github.com').exists())

    def test_redirect_and_pkce_validation(self):
        response=self.client.get('/api/auth/oauth/url/',{'provider':'github','redirect_uri':'https://attacker.invalid/callback','code_challenge':'a'*43})
        self.assertEqual(response.status_code,400)
        data=self.begin();data['code_verifier']='b'*64
        with patch.object(OAuthService,'exchange') as exchange:
            self.assertEqual(self.client.post('/api/auth/oauth/callback/',data).status_code,400)
            exchange.assert_not_called()

    def test_state_is_single_use(self):
        data=self.begin()
        with patch.object(OAuthService,'exchange',return_value=self.profile()) as exchange:
            response=self.client.post('/api/auth/oauth/callback/',data)
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(self.client.post('/api/auth/oauth/callback/',data).status_code,400)
            self.assertEqual(exchange.call_count,1)
        self.assertFalse(User.objects.get(email='new@example.com').has_usable_password())

    def test_expired_state(self):
        data=self.begin();OAuthAttempt.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.client.post('/api/auth/oauth/callback/',data).status_code,400)

    def test_provider_mixup(self):
        data=self.begin();data['provider']='google'
        self.assertEqual(self.client.post('/api/auth/oauth/callback/',data).status_code,400)

    def test_email_collision_does_not_link_accounts(self):
        data=self.begin()
        with patch.object(OAuthService,'exchange',return_value=self.profile(self.user.email)):
            self.assertEqual(self.client.post('/api/auth/oauth/callback/',data).status_code,400)
        self.assertFalse(SocialIdentity.objects.filter(user=self.user).exists())

    def test_authenticated_link_and_subject_based_login(self):
        data=self.begin(authenticated=True)
        with patch.object(OAuthService,'exchange',return_value=self.profile('different@example.com')):
            self.assertEqual(self.client.post('/api/auth/oauth/callback/',data).status_code,200)
        self.client.force_authenticate(user=None)
        data=self.begin()
        with patch.object(OAuthService,'exchange',return_value=self.profile('changed@example.com')):
            response=self.client.post('/api/auth/oauth/callback/',data)
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(response.data['user']['id'],str(self.user.pk))

    def test_registration_password_validation_and_verification(self):
        self.assertEqual(self.client.post('/api/auth/register/',dict(email='new@example.com',password='12345678')).status_code,400)
        response=self.client.post('/api/auth/register/',dict(email='new@example.com',password='StrongTestPassword!936'))
        self.assertEqual(response.status_code,201,response.data);self.assertNotIn('token',response.data)
        self.assertEqual(len(mail.outbox),1)
        link=mail.outbox[0].body.split()[-1];ticket=parse_qs(urlparse(link).query)['verify'][0]
        self.assertEqual(self.client.post('/api/auth/login/',dict(email='new@example.com',password='StrongTestPassword!936')).status_code,403)
        self.assertEqual(self.client.post('/api/auth/verify-email/',{'ticket':ticket}).status_code,200)
        self.assertEqual(self.client.post('/api/auth/verify-email/',{'ticket':ticket}).status_code,400)
        self.assertEqual(self.client.post('/api/auth/login/',dict(email='new@example.com',password='StrongTestPassword!936')).status_code,200)

    def test_password_reset_revokes_tokens(self):
        Token.objects.create(user=self.user)
        response=self.client.post('/api/auth/password-reset/',{'email':self.user.email})
        self.assertEqual(response.status_code,200)
        query=parse_qs(urlparse(mail.outbox[0].body.split()[-1]).query)
        data=dict(user=query['reset_user'][0],token=query['reset_token'][0],password='ChangedPassword!844')
        self.assertEqual(self.client.post('/api/auth/password-reset/confirm/',data).status_code,200)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.post('/api/auth/password-reset/confirm/',data).status_code,400)

    @override_settings(API_TOKEN_TTL=60)
    def test_expired_api_token(self):
        token=Token.objects.create(user=self.user)
        Token.objects.filter(pk=token.pk).update(created=timezone.now()-timedelta(minutes=2))
        self.client.credentials(HTTP_AUTHORIZATION='Token '+token.key)
        self.assertEqual(self.client.get('/api/auth/me/').status_code,401)


class AuthorizationTests(Fixtures):
    def test_cross_user_repository_and_ai_config(self):
        connection=GitHubConnection.objects.create(user=self.other,github_user_id='7',github_username='other')
        repository=Repository.objects.create(connection=connection,github_repo_id='8',full_name='other/private',allowed_paths=['src/'])
        config=AIProviderConfig.objects.create(user=self.other)
        data=self.data();data['repository']=str(repository.pk)
        self.assertEqual(self.client.post('/api/automations/',data).status_code,400)
        self.assertEqual(self.client.post('/api/automations/',self.data(ai_config=str(config.pk))).status_code,400)
        self.assertEqual(self.client.patch(f'/api/automations/{self.auto.pk}/',{'repository':str(repository.pk)}).status_code,400)

    def test_worker_rechecks_relationship_ownership(self):
        self.connection.user=self.other;self.connection.save()
        with patch('apps.executions.tasks.GitHubAppService.fetch_repository_context') as fetch:
            execute_automation_task(str(self.auto.pk),'foreign')
            fetch.assert_not_called()
        self.assertEqual(Execution.objects.get(scheduled_slot='foreign').status,'FAILED')

    def test_connection_identity_cannot_be_created_by_client(self):
        self.assertEqual(self.client.post('/api/github/connections/',{'installation_id':'12345'}).status_code,405)

    def test_installation_claim_requires_verified_ownership(self):
        with patch.object(GitHubAppService,'verify_installation_access',side_effect=GitHubAPIError('Access denied')):
            response=self.client.post('/api/github/callback/',dict(connection_id=str(self.connection.pk),installation_id='12345'))
        self.assertEqual(response.status_code,403)
        self.assertFalse(GitHubConnection.objects.filter(installation_id='12345').exists())

    def test_repository_identity_is_read_only(self):
        self.client.patch(f'/api/github/repositories/{self.repo.pk}/',{'full_name':'other/repo','default_branch':'production'})
        self.repo.refresh_from_db();self.assertEqual(self.repo.full_name,'owner/repo');self.assertEqual(self.repo.default_branch,'main')

    def test_other_user_cannot_read_execution(self):
        execution=Execution.objects.create(automation=self.auto,scheduled_slot='private')
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(f'/api/executions/{execution.pk}/').status_code,404)


@override_settings(GITHUB_WEBHOOK_SECRET='unit-test-webhook-secret')
class WebhookTests(Fixtures):
    def test_missing_or_malformed_signature_rejected(self):
        self.client=APIClient()
        for signature in ['', 'invalid', 'sha256=x=y', 'sha1='+'a'*64]:
            response=self.client.post('/api/github/webhook/',{'action':'deleted','installation':{'id':99}},format='json',HTTP_X_HUB_SIGNATURE_256=signature,HTTP_X_GITHUB_EVENT='installation')
            self.assertEqual(response.status_code,403)
        self.assertTrue(GitHubConnection.objects.filter(pk=self.connection.pk).exists())

    def test_signed_deletion_preserves_audit_history_and_deduplicates(self):
        execution=Execution.objects.create(automation=self.auto,scheduled_slot='audit')
        self.connection.installation_id='99';self.connection.save()
        body=json.dumps({'action':'deleted','installation':{'id':99}}).encode()
        signature='sha256='+hmac.new(b'unit-test-webhook-secret',body,hashlib.sha256).hexdigest()
        self.client=APIClient()
        response=self.client.post('/api/github/webhook/',body,content_type='application/json',HTTP_X_HUB_SIGNATURE_256=signature,HTTP_X_GITHUB_EVENT='installation')
        self.assertEqual(response.status_code,200,response.data)
        self.connection.refresh_from_db();self.auto.refresh_from_db();self.repo.refresh_from_db()
        self.assertFalse(self.connection.is_active);self.assertFalse(self.auto.enabled);self.assertFalse(self.repo.is_active)
        self.assertTrue(Execution.objects.filter(pk=execution.pk).exists())
        response=self.client.post('/api/github/webhook/',body,content_type='application/json',HTTP_X_HUB_SIGNATURE_256=signature,HTTP_X_GITHUB_EVENT='installation')
        self.assertEqual(response.data['status'],'already received')


class SchedulingTests(Fixtures):
    def test_schedule_created_updated_and_disabled(self):
        task=PeriodicTask.objects.get(name=f'automation:{self.auto.pk}')
        self.assertEqual(task.crontab.hour,'9')
        response=self.client.patch(f'/api/automations/{self.auto.pk}/',dict(cron_expression='37 14 * * *',timezone='Asia/Kolkata'))
        self.assertEqual(response.status_code,200,response.data)
        task.refresh_from_db();self.assertEqual(task.crontab.minute,'37');self.assertEqual(str(task.crontab.timezone),'Asia/Kolkata')
        self.client.patch(f'/api/automations/{self.auto.pk}/',{'enabled':False})
        task.refresh_from_db();self.assertFalse(task.enabled)

    def test_invalid_configuration(self):
        for values in [dict(cron_expression='invalid'),dict(cron_expression='99 * * * *'),dict(timezone='Moon/City'),dict(max_files=-1),dict(branch_strategy='DIRECT_PUSH',require_approval=False),dict(allowed_paths=[])]:
            with self.subTest(values=values):
                self.assertEqual(self.client.post('/api/automations/',self.data(**values),format='json').status_code,400)

    def test_due_slot_is_stable_and_missed_runs_are_skipped(self):
        due=timezone.now().replace(second=0,microsecond=0)
        Automation.objects.filter(pk=self.auto.pk).update(next_run_at=due)
        with patch('apps.executions.tasks.enqueue_execution') as enqueue:
            dispatch_scheduled_automation(str(self.auto.pk));dispatch_scheduled_automation(str(self.auto.pk))
            self.assertEqual(enqueue.call_count,1)
        self.assertEqual(self.auto.executions.count(),1)
        Automation.objects.filter(pk=self.auto.pk).update(next_run_at=due-timedelta(hours=1))
        with patch('apps.executions.tasks.enqueue_execution') as enqueue:
            dispatch_scheduled_automation(str(self.auto.pk));enqueue.assert_not_called()


class ExecutionTests(Fixtures):
    def test_generation_records_immutable_proposal_and_real_diff(self):
        run=self.generate()
        self.assertEqual(run.status,'AWAITING_APPROVAL',run.error_message)
        self.assertTrue(run.proposal_hash)
        self.assertEqual(run.snapshot['base_tree_sha'],'BASE_TREE')
        self.assertIn('@@',run.generated_files.get().diff_patch)
        self.assertEqual(run.snapshot['proposal']['commit_message'],'feat: add example')

    def test_duplicate_worker_delivery_does_not_generate(self):
        Execution.objects.create(automation=self.auto,scheduled_slot='claimed',status='RUNNING')
        with patch('apps.executions.tasks.get_ai_adapter') as adapter:
            execute_automation_task(str(self.auto.pk),'claimed');adapter.assert_not_called()

    def test_approval_is_atomic_and_queues_exact_proposal(self):
        run=self.generate()
        with patch('apps.executions.tasks.execute_automation_task.delay') as enqueue:
            response=self.client.post(f'/api/executions/{run.pk}/approve/',{'proposal_hash':run.proposal_hash})
            self.assertEqual(response.status_code,202,response.data)
            self.assertEqual(self.client.post(f'/api/executions/{run.pk}/approve/',{'proposal_hash':run.proposal_hash}).status_code,409)
            self.assertEqual(enqueue.call_count,1)

    def test_stale_approval_and_wrong_hash_rejected(self):
        run=self.generate()
        self.assertEqual(self.client.post(f'/api/executions/{run.pk}/approve/',{'proposal_hash':'wrong'}).status_code,409)
        self.auto.branch_strategy='DIRECT_PUSH';self.auto.save()
        self.assertEqual(self.client.post(f'/api/executions/{run.pk}/approve/',{'proposal_hash':run.proposal_hash}).status_code,409)

    def test_successful_pipeline_uses_real_publisher_contract(self):
        self.auto.require_approval=False;self.auto.save()
        result=type('Result',(),dict(success=True,branch_name='automation/test',commit_sha='REAL_MOCK_SHA',pull_request_url='https://github.com/owner/repo/pull/1',pull_request_number=1))()
        with patch('apps.executions.tasks.GitPublishingService.publish',return_value=result) as publish:
            run=self.generate()
        self.assertEqual(run.status,'SUCCESS',run.error_message)
        self.assertEqual(publish.call_args.kwargs['base_tree_sha'],'BASE_TREE')
        self.assertEqual(run.published_change.commit_sha,'REAL_MOCK_SHA')

    def test_queue_failure_does_not_fall_back_to_sync(self):
        with patch('apps.executions.tasks.execute_automation_task.delay',side_effect=ConnectionError),patch('apps.executions.tasks.get_ai_adapter') as adapter:
            response=self.client.post(f'/api/automations/{self.auto.pk}/run/')
            self.assertEqual(response.status_code,503,response.data);adapter.assert_not_called()
        self.assertEqual(Execution.objects.get().status,'FAILED')

    def test_manual_request_idempotency(self):
        headers={'HTTP_IDEMPOTENCY_KEY':str(uuid.uuid4())}
        with patch('apps.executions.tasks.execute_automation_task.delay') as enqueue:
            first=self.client.post(f'/api/automations/{self.auto.pk}/run/',**headers)
            second=self.client.post(f'/api/automations/{self.auto.pk}/run/',**headers)
            self.assertEqual(first.status_code,202,first.data);self.assertEqual(second.status_code,200,second.data)
            self.assertEqual(first.data['id'],second.data['id']);self.assertEqual(enqueue.call_count,1)

    def test_disabled_queued_run_becomes_failed(self):
        Execution.objects.create(automation=self.auto,scheduled_slot='disabled')
        self.auto.enabled=False;self.auto.save()
        execute_automation_task(str(self.auto.pk),'disabled')
        self.assertEqual(Execution.objects.get().status,'FAILED')

    def test_success_cannot_be_retried_and_failed_retry_keeps_identity(self):
        run=Execution.objects.create(automation=self.auto,scheduled_slot='retry',status='SUCCESS')
        self.assertEqual(self.client.post(f'/api/executions/{run.pk}/retry/').status_code,409)
        run.status='FAILED';run.save()
        with patch('apps.executions.tasks.execute_automation_task.delay'):
            response=self.client.post(f'/api/executions/{run.pk}/retry/')
        self.assertEqual(response.status_code,202,response.data);self.assertEqual(response.data['id'],str(run.pk))
        self.assertEqual(Execution.objects.count(),1)

    def test_worker_interruption_recovery(self):
        run=Execution.objects.create(automation=self.auto,scheduled_slot='interrupted',status='PUBLISHING',heartbeat_at=timezone.now()-timedelta(minutes=20))
        recover_interrupted_executions();run.refresh_from_db();self.assertEqual(run.status,'FAILED')

    def test_list_omits_large_file_content(self):
        self.generate()
        response=self.client.get('/api/executions/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertNotIn('generated_files',response.data['results'][0])


class PublisherTests(Fixtures):
    def run_publish(self,strategy='PULL_REQUEST',state=None):
        state=state if state is not None else {}
        calls=[]
        def handle(request):
            path=request.url.path;method=request.method
            data=json.loads(request.content) if request.content else {}
            calls.append((method,path,data))
            def respond(data,status=200):return httpx.Response(status,json=data)
            if path.endswith('/git/commits/BASE_COMMIT'):return respond({'tree':{'sha':'BASE_TREE'}})
            if path.endswith('/git/blobs'):return respond({'sha':'BLOB'},201)
            if path.endswith('/git/trees'):return respond({'sha':'NEW_TREE'},201)
            if '/git/ref/heads/automation/' in path:
                return respond({'object':{'sha':'NEW_COMMIT'}}) if state.get('branch') else respond({'message':'Not Found'},404)
            if path.endswith('/git/commits/NEW_COMMIT'):
                return respond({'tree':{'sha':'WRONG_TREE' if state.get('collision') else 'NEW_TREE'},'message':'feat: add example','parents':[{'sha':'BASE_COMMIT'}]})
            if path.endswith('/git/ref/heads/main'):return respond({'object':{'sha':state.get('head','BASE_COMMIT')}})
            if path.endswith('/git/commits'):
                return respond({'sha':'NEW_COMMIT'},201)
            if path.endswith('/git/refs'):
                state['branch']=True
                return respond({'object':{'sha':'NEW_COMMIT'}},201)
            if path.endswith('/pulls'):
                pull={'number':1,'html_url':'https://github.com/owner/repo/pull/1','head':{'sha':'NEW_COMMIT'}}
                if method=='GET':return respond([pull] if state.get('pr') else [])
                state['pr']=True
                if state.get('timeout_pr'):
                    raise httpx.ReadTimeout('ambiguous response',request=request)
                return respond(pull,201)
            if path.endswith('/git/refs/heads/main'):
                if state.get('deny_push'):return respond({'message':'Forbidden'},403)
                state['head']='NEW_COMMIT';return respond({'object':{'sha':'NEW_COMMIT'}})
            raise AssertionError(f'Unexpected GitHub request: {method} {path}')
        client=httpx.Client(transport=httpx.MockTransport(handle))
        with patch('apps.git_publishing.publisher.httpx.Client',return_value=client), \
             patch.object(GitHubAppService,'get_effective_token',return_value='mock-token'):
            result=GitPublishingService.publish(self.repo,proposal(),strategy,execution_id='stable-id',base_sha='BASE_COMMIT',base_tree_sha='BASE_TREE',commit_date='2026-11-17T09:00:00+00:00')
        return result,calls

    def test_base_tree_and_confirmed_pr(self):
        result,calls=self.run_publish()
        self.assertTrue(result.success,result.error)
        tree=next(data for method,path,data in calls if path.endswith('/git/trees'))
        self.assertEqual(tree['base_tree'],'BASE_TREE')

    def test_denied_direct_push_is_failure(self):
        result,_=self.run_publish('DIRECT_PUSH',{'deny_push':True})
        self.assertFalse(result.success);self.assertIn('403',result.error)

    def test_direct_push_checks_final_ref(self):
        result,calls=self.run_publish('DIRECT_PUSH')
        self.assertTrue(result.success,result.error);self.assertEqual(result.branch_name,'main')
        self.assertEqual(calls[-1][1],'/repos/owner/repo/git/ref/heads/main')

    def test_retry_reuses_existing_branch_and_pr(self):
        state={}
        first,_=self.run_publish(state=state)
        second,calls=self.run_publish(state=state)
        self.assertTrue(first.success);self.assertTrue(second.success,second.error)
        self.assertFalse(any(method=='POST' and path.endswith(('/git/commits','/git/refs','/pulls')) for method,path,_ in calls))

    def test_ambiguous_pr_response_is_reconciled(self):
        result,_=self.run_publish(state={'timeout_pr':True})
        self.assertTrue(result.success,result.error)

    def test_stale_target_and_branch_collision_fail_closed(self):
        for state in [{'head':'CHANGED_COMMIT'},{'branch':True,'collision':True}]:
            with self.subTest(state=state):
                result,_=self.run_publish(state=state);self.assertFalse(result.success)

    def test_missing_credentials_never_simulates_success(self):
        self.connection.encrypted_access_token='';self.connection.save()
        result=GitPublishingService.publish(self.repo,proposal(),execution_id='id',base_sha='BASE_COMMIT',base_tree_sha='BASE_TREE',commit_date='2026-11-17T09:00:00+00:00')
        self.assertFalse(result.success)

class AdditionalRegressionTests(Fixtures):
    def test_timezone_next_occurrence_preserves_local_minutes(self):
        from datetime import datetime, timezone as tz
        from apps.automations.scheduling import next_scheduled_at
        start=datetime(2026,11,17,0,0,tzinfo=tz.utc)
        self.assertEqual(next_scheduled_at('37 9 * * *','Asia/Kolkata',start), datetime(2026,11,17,4,7,tzinfo=tz.utc))

    def test_dst_gap_is_skipped_and_fold_slots_deduplicate(self):
        from datetime import datetime, timezone as tz
        from apps.automations.scheduling import next_scheduled_at
        start=datetime(2026,3,8,5,0,tzinfo=tz.utc)
        self.assertEqual(next_scheduled_at('30 2 * * *','America/New_York',start), datetime(2026,3,9,6,30,tzinfo=tz.utc))
        self.auto.timezone='America/New_York';self.auto.cron_expression='30 1 * * *';self.auto.save()
        with patch('apps.executions.tasks.enqueue_execution') as enqueue:
            for due in [datetime(2026,11,1,5,30,tzinfo=tz.utc),datetime(2026,11,1,6,30,tzinfo=tz.utc)]:
                Automation.objects.filter(pk=self.auto.pk).update(next_run_at=due)
                with patch('apps.executions.tasks.timezone.now',return_value=due):
                    dispatch_scheduled_automation(str(self.auto.pk))
            self.assertEqual(enqueue.call_count,1)

    def test_impossible_calendar_rejected(self):
        response=self.client.post('/api/automations/',self.data(cron_expression='0 9 31 2 *'))
        self.assertEqual(response.status_code,400,response.data)

    @override_settings(MAX_DAILY_EXECUTIONS=1)
    def test_generation_budget_counts_attempts(self):
        self.generate('first')
        with patch('apps.executions.tasks.GitHubAppService.fetch_repository_context',return_value=self.context), patch('apps.executions.tasks.get_ai_adapter') as adapter:
            execute_automation_task(str(self.auto.pk),'second')
            adapter.assert_not_called()
        self.assertEqual(Execution.objects.get(scheduled_slot='second').status,'REJECTED')

    def test_saved_key_is_encrypted_and_provider_activation_is_explicit(self):
        response=self.client.post('/api/ai-configs/',dict(provider='gemini',model_name='gemini-2.5-flash',api_key='fake-key-value'))
        self.assertEqual(response.status_code,201,response.data)
        self.assertNotIn('api_key',response.data)
        created=AIProviderConfig.objects.get(pk=response.data['id'])
        self.assertNotEqual(created.encrypted_api_key,'fake-key-value');self.assertEqual(created.get_api_key(),'fake-key-value')
        self.config.refresh_from_db();self.assertFalse(self.config.is_active)

    def test_gemini_routes_to_google_endpoint(self):
        from apps.ai_engine.adapters.factory import get_ai_adapter
        self.config.provider='gemini'
        with patch('apps.ai_engine.adapters.factory.OpenAIAdapter') as adapter:
            get_ai_adapter(self.config)
            self.assertEqual(adapter.call_args.kwargs['base_url'],'https://generativelanguage.googleapis.com/v1beta/openai/')

    def test_mutated_generated_content_cannot_publish(self):
        run=self.generate()
        with patch('apps.executions.tasks.execute_automation_task.delay'):
            self.client.post(f'/api/executions/{run.pk}/approve/',{'proposal_hash':run.proposal_hash})
        run.generated_files.update(new_content='def different(value):\n    return value + 100\n')
        with patch('apps.executions.tasks.GitPublishingService.publish') as publish:
            execute_automation_task(str(self.auto.pk),run.scheduled_slot);publish.assert_not_called()
        run.refresh_from_db();self.assertEqual(run.status,'FAILED')

    def test_original_source_is_required_for_modification(self):
        self.context['entries']={'src/example.py':{'mode':'100644','type':'blob','sha':'OLD_BLOB'}}
        run=self.generate(value=proposal(kind='MODIFY'))
        self.assertEqual(run.status,'REJECTED')
        self.context['source_files']={'src/example.py':'def example(value):\n    return value\n'}
        run=self.generate('read-source',value=proposal(kind='MODIFY'))
        self.assertEqual(run.status,'AWAITING_APPROVAL',run.error_message)
        self.assertIn('-    return value',run.generated_files.get().diff_patch)

    def test_readiness_reports_dependency_failure(self):
        with patch('commitflow.urls.cache.get',return_value=None):
            self.assertEqual(self.client.get('/api/health/').status_code,503)

    def test_google_unverified_email_is_rejected(self):
        def handler(request):
            return httpx.Response(200,json={'access_token':'fake-token'} if request.method=='POST' else {'sub':'99','email':'new@example.com','email_verified':False})
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with override_settings(GOOGLE_CLIENT_ID='configured',GOOGLE_CLIENT_SECRET='configured'), patch('apps.authentication.oauth.httpx.Client',return_value=client):
            with self.assertRaises(ValueError):OAuthService.exchange('google','code','http://localhost:3000/auth/callback','a'*64)

    def test_oauth_payload_types_fail_safely(self):
        client=APIClient()
        self.assertEqual(client.post('/api/auth/oauth/callback/',[],format='json').status_code,400)
        self.assertEqual(client.post('/api/auth/password-reset/confirm/',dict(user={},token=[],password={}),format='json').status_code,400)

    def test_installation_ownership_service_rejects_another_account(self):
        def handler(request):
            if request.url.path=='/user':return httpx.Response(200,json={'id':42})
            return httpx.Response(200,json={'app_id':1,'account':{'type':'User','id':999}})
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with override_settings(GITHUB_APP_ID='1'), patch.object(GitHubAppService,'get_app_jwt',return_value='mock-app-token'), patch('apps.github_integration.services.httpx.Client',return_value=client):
            with self.assertRaises(GitHubAPIError):GitHubAppService.verify_installation_access(self.connection,'123')

    def test_app_repository_sync_does_not_require_oauth_permissions_field(self):
        self.connection.installation_id='123';self.connection.save()
        def handler(request):
            return httpx.Response(200,json={'repositories':[{'id':100,'full_name':'owner/app-repo','default_branch':'main'}]})
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with patch.object(GitHubAppService,'get_effective_token',return_value='installation-token'), patch('apps.github_integration.services.httpx.Client',return_value=client):
            repositories=GitHubAppService.sync_user_repositories(self.user)
        self.assertEqual([repo.full_name for repo in repositories],['owner/app-repo'])

    def test_repository_sync_paginates_and_deactivates_removed_repositories(self):
        entries=[dict(id=i+100,full_name=f'owner/repo-{i}',default_branch='main',permissions={'push':True}) for i in range(101)]
        def handler(request):
            page=int(request.url.params['page']);return httpx.Response(200,json=entries[(page-1)*100:page*100])
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with patch.object(GitHubAppService,'get_effective_token',return_value='mock-token'), patch('apps.github_integration.services.httpx.Client',return_value=client):
            repositories=GitHubAppService.sync_user_repositories(self.user)
        self.assertEqual(len(repositories),101);self.repo.refresh_from_db();self.assertFalse(self.repo.is_active)

    def test_sandbox_is_offline_bounded_and_requires_executed_tests(self):
        from types import SimpleNamespace
        from apps.validation.sandbox import run_python_tests
        with patch('apps.validation.sandbox.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Ran 1 test in 0.001s\nOK')) as execute:
            result=run_python_tests({'tests/test_example.py':'import unittest\nclass TestExample(unittest.TestCase):\n def test_example(self): self.assertEqual(1+1,2)\n'})
            self.assertTrue(result['passed'])
            command=execute.call_args_list[0].args[0]
            for required in ['--network=none','--read-only','--cap-drop=ALL','--pull=never','--memory=256m','--user=65534:65534']:
                self.assertIn(required,command)
            self.assertNotIn('fake-oauth-token',' '.join(command))
        with patch('apps.validation.sandbox.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='Ran 0 tests\nOK')):
            self.assertFalse(run_python_tests({'tests/test_empty.py':'# no tests'})['passed'])

    @override_settings(ENABLE_PYTHON_SANDBOX=True)
    def test_enabled_but_failed_sandbox_rejects_proposal(self):
        with patch('apps.validation.sandbox.run_python_tests',return_value={'passed':False,'message':'Sandbox unavailable.'}):
            run=self.generate()
        self.assertEqual(run.status,'REJECTED');self.assertFalse(run.validation_results['is_valid'])

class FinalBoundaryTests(Fixtures):
    def test_revoked_installation_owner_cannot_mint_tokens(self):
        installation=GitHubConnection.objects.create(user=self.user,github_user_id='42',github_username='owner',installation_id='123')
        self.connection.is_active=False;self.connection.save()
        with patch.object(GitHubAppService,'get_installation_token') as mint:
            with self.assertRaises(GitHubAPIError):GitHubAppService.get_effective_token(installation)
            mint.assert_not_called()

    def test_installation_authorization_is_rechecked_before_token_issue(self):
        installation=GitHubConnection.objects.create(user=self.user,github_user_id='42',github_username='owner',installation_id='123')
        with patch.object(GitHubAppService,'verify_installation_access',side_effect=GitHubAPIError('Membership revoked')), patch.object(GitHubAppService,'get_installation_token') as mint:
            with self.assertRaises(GitHubAPIError):GitHubAppService.get_effective_token(installation)
            mint.assert_not_called()

    def test_parent_file_cannot_be_replaced_with_a_directory(self):
        self.context['entries']={'src/link':{'type':'blob','mode':'120000','sha':'SYMLINK'}}
        run=self.generate(value=proposal(path='src/link/example.py'))
        self.assertEqual(run.status,'REJECTED')

    def test_missing_approval_field_preserves_safe_default_for_forms(self):
        response=self.client.post('/api/automations/',self.data())
        self.assertEqual(response.status_code,201,response.data)
        self.assertTrue(response.data['require_approval'])

    def test_expired_token_does_not_block_public_login(self):
        client=APIClient();token=Token.objects.create(user=self.user)
        Token.objects.filter(pk=token.pk).update(created=timezone.now()-timedelta(days=7))
        client.credentials(HTTP_AUTHORIZATION='Token '+token.key)
        response=client.post('/api/auth/login/',dict(email=self.user.email,password='StrongTestPassword!936'))
        self.assertEqual(response.status_code,200,response.data)

    def test_overlapping_proposed_file_paths_rejected(self):
        value=proposal(path='src/nested')
        value.files.append(ProposedFile(path='src/nested/child.py',content='def child(value):\n    return value + 1\n'))
        self.assertFalse(ValidationEngine.validate(value,['src/']).is_valid)

    def test_source_context_is_pinned_and_sensitive_files_are_not_forwarded(self):
        paths=[]
        def handler(request):
            paths.append(request.url.path)
            if '/git/ref/' in request.url.path:return httpx.Response(200,json={'object':{'sha':'BASE_COMMIT'}})
            if '/git/commits/' in request.url.path:return httpx.Response(200,json={'tree':{'sha':'BASE_TREE'}})
            if '/git/trees/' in request.url.path:return httpx.Response(200,json={'tree':[
                {'path':'src/example.py','type':'blob','mode':'100644','sha':'SOURCE','size':40},
                {'path':'src/.env.production','type':'blob','mode':'100644','sha':'SECRET','size':40}]})
            if request.url.path.endswith('/SOURCE'):
                return httpx.Response(200,json={'encoding':'base64','size':40,'content':base64.b64encode(b'def example(value):\n    return value + 1\n').decode()})
            raise AssertionError('Sensitive file should never be fetched')
        client=httpx.Client(transport=httpx.MockTransport(handler))
        with patch('apps.github_integration.services.httpx.Client',return_value=client):
            context=GitHubAppService.fetch_repository_context(self.repo)
        self.assertEqual(context['base_sha'],'BASE_COMMIT');self.assertEqual(context['base_tree_sha'],'BASE_TREE')
        self.assertEqual(list(context['source_files']),['src/example.py'])
        self.assertIn('/repos/owner/repo/git/trees/BASE_TREE',paths)

class ServiceFailureTests(Fixtures):
    def test_email_failure_preserves_account_for_resend(self):
        client=APIClient()
        with patch('apps.authentication.views.send_mail',side_effect=OSError('SMTP unavailable')):
            response=client.post('/api/auth/register/',dict(email='mailfailure@example.com',password='StrongTestPassword!936'))
        self.assertEqual(response.status_code,503,response.data)
        self.assertTrue(User.objects.filter(email='mailfailure@example.com',email_verified=False).exists())
        self.assertEqual(client.post('/api/auth/resend-verification/',{'email':'mailfailure@example.com'}).status_code,200)
        self.assertEqual(len(mail.outbox),1)

    def test_installation_and_approval_reject_invalid_payload_types(self):
        self.assertEqual(self.client.post('/api/github/callback/',dict(connection_id={},installation_id=[]),format='json').status_code,400)
        run=self.generate()
        self.assertEqual(self.client.post(f'/api/executions/{run.pk}/approve/',[],format='json').status_code,400)
