"""Verify that legacy credentials/proposals are quarantined without deleting audit data."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UpgradeTests(TransactionTestCase):
    def test_legacy_installation_and_simulated_publication_are_quarantined(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        legacy = [
            ('authentication', '0002_user_auth_provider_user_avatar_url_user_provider_id'),
            ('github_integration', '0001_initial'),
            ('automations', '0001_initial'),
            ('executions', '0001_initial'),
        ]
        try:
            executor.migrate(legacy)
            old = executor.loader.project_state(legacy).apps
            User = old.get_model('authentication', 'User')
            Connection = old.get_model('github_integration', 'GitHubConnection')
            Repo = old.get_model('github_integration', 'Repository')
            Auto = old.get_model('automations', 'Automation')
            Execution = old.get_model('executions', 'Execution')
            Published = old.get_model('executions', 'PublishedChange')
            user = User.objects.create(email='upgrade@example.com', auth_provider='github', provider_id='42')
            github = Connection.objects.create(user=user, github_user_id='42', github_username='owner',
                                                installation_id='123', encrypted_access_token='legacy-ciphertext')
            repo = Repo.objects.create(connection=github, github_repo_id='1', full_name='owner/repo', allowed_paths=['src/'])
            automation = Auto.objects.create(user=user, repository=repo, title='Legacy', instructions='Useful code', require_approval=False)
            waiting = Execution.objects.create(automation=automation, scheduled_slot='waiting', status='AWAITING_APPROVAL')
            simulated = Execution.objects.create(automation=automation, scheduled_slot='simulated', status='SUCCESS')
            Published.objects.create(execution=simulated, branch_name='automation/old', commit_sha='simulated-123', commit_message='Simulated')
            MigrationExecutor(connection).migrate(latest)
            from apps.github_integration.models import GitHubConnection
            from apps.automations.models import Automation
            from apps.executions.models import Execution as CurrentExecution
            from apps.authentication.models import SocialIdentity
            migrated = GitHubConnection.objects.get(pk=github.pk)
            rule = Automation.objects.get(pk=automation.pk)
            self.assertFalse(migrated.is_active)
            self.assertEqual(migrated.encrypted_access_token, '')
            self.assertFalse(rule.enabled)
            self.assertTrue(rule.require_approval)
            self.assertEqual(CurrentExecution.objects.get(pk=waiting.pk).status, 'REJECTED')
            self.assertEqual(CurrentExecution.objects.get(pk=simulated.pk).status, 'REJECTED')
            self.assertTrue(SocialIdentity.objects.filter(user_id=user.pk, provider='github', subject='42').exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
