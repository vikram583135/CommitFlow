"""Exercise real PostgreSQL row locks; SQLite is not a concurrency substitute."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from django.db import connection, close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from apps.authentication.models import User
from apps.github_integration.models import GitHubConnection, Repository
from apps.automations.models import Automation
from apps.executions.models import Execution
from apps.executions.tasks import configuration, snapshot_digest, execute_automation_task


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locks')
class PostgreSQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='concurrency@example.com', password='TestPassword!936', email_verified=True)
        github = GitHubConnection.objects.create(user=self.user, github_user_id='42', github_username='owner', installation_id='oauth_user_account')
        repo = Repository.objects.create(connection=github, github_repo_id='1', full_name='owner/repo', allowed_paths=['src/'])
        self.auto = Automation.objects.create(user=self.user, repository=repo, title='Concurrency', instructions='Useful code')

    def test_simultaneous_approvals_enqueue_once(self):
        snapshot = {'configuration': configuration(self.auto)}
        execution = Execution.objects.create(automation=self.auto, scheduled_slot='approval-race', status='AWAITING_APPROVAL',
            snapshot=snapshot, proposal_hash=snapshot_digest(snapshot))
        barrier = Barrier(2)

        def approve():
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=self.user.pk))
                barrier.wait(timeout=10)
                return client.post(f'/api/executions/{execution.pk}/approve/', {'proposal_hash': execution.proposal_hash}).status_code
            finally:
                close_old_connections()

        with patch('apps.executions.tasks.execute_automation_task.delay') as enqueue, ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(approve) for _ in range(2)]
            self.assertEqual(sorted(future.result(timeout=15) for future in futures), [202, 409])
            self.assertEqual(enqueue.call_count, 1)

    def test_simultaneous_worker_deliveries_claim_once(self):
        Execution.objects.create(automation=self.auto, scheduled_slot='worker-race')
        barrier = Barrier(2)

        def execute():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return execute_automation_task(str(self.auto.pk), 'worker-race')
            finally:
                close_old_connections()

        # No AI configuration: exactly one claim rejects it; the duplicate skips.
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(execute) for _ in range(2)]
            messages = [future.result(timeout=15) for future in futures]
        self.assertEqual(sum('already claimed' in message for message in messages), 1)
        self.assertEqual(Execution.objects.get(scheduled_slot='worker-race').status, 'REJECTED')
