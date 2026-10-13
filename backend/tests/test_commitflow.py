from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.common.encryption import encrypt_secret, decrypt_secret, mask_secret
from apps.github_integration.models import GitHubConnection, Repository
from apps.ai_engine.models import AIProviderConfig
from apps.ai_engine.adapters.schemas import CodeProposal, ProposedFile
from apps.validation.validator import ValidationEngine
from apps.automations.models import Automation
from apps.executions.tasks import execute_automation_task
from apps.executions.models import Execution

User = get_user_model()

class EncryptionTests(TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        plain = "ghp_1234567890abcdefABCDEF1234567890"
        encrypted = encrypt_secret(plain)
        self.assertNotEqual(plain, encrypted)
        decrypted = decrypt_secret(encrypted)
        self.assertEqual(plain, decrypted)

    def test_mask_secret(self):
        secret = "sk-proj-1234567890abcdef"
        masked = mask_secret(secret, visible_suffix_len=4)
        self.assertTrue(masked.startswith("••••••••"))
        self.assertTrue(masked.endswith("cdef"))

class ValidationEngineTests(TestCase):
    def test_path_traversal_rejection(self):
        proposal = CodeProposal(
            summary="Attempt directory escape",
            commit_message="hack: evil traversal",
            pr_title="Evil PR",
            pr_body="Attempting path traversal",
            files=[
                ProposedFile(path="../../etc/passwd", change_type="CREATE", content="root:x:0:0:root:/root:/bin/bash\n1234567890")
            ]
        )
        res = ValidationEngine.validate(proposal, allowed_paths=["src/"])
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Path traversal" in err for err in res.errors))

    def test_blacklist_rejection(self):
        proposal = CodeProposal(
            summary="Attempt .env edit",
            commit_message="chore: update env",
            pr_title="Update Env",
            pr_body="Testing env file rejection",
            files=[
                ProposedFile(path=".env.production", change_type="CREATE", content="SECRET_KEY=leaked_production_key_12345")
            ]
        )
        res = ValidationEngine.validate(proposal, allowed_paths=["src/"])
        self.assertFalse(res.is_valid)
        self.assertTrue(any("restricted file" in err for err in res.errors))

    def test_allowed_path_boundary(self):
        proposal = CodeProposal(
            summary="File outside allowed prefix",
            commit_message="feat: outside allowed paths",
            pr_title="PR outside",
            pr_body="Tests allowed paths boundaries",
            files=[
                ProposedFile(path="infra/config.yaml", change_type="CREATE", content="key: value with more than twenty characters")
            ]
        )
        res = ValidationEngine.validate(proposal, allowed_paths=["src/", "tests/"])
        self.assertFalse(res.is_valid)
        self.assertTrue(any("outside allowed paths" in err for err in res.errors))

    def test_valid_proposal(self):
        proposal = CodeProposal(
            summary="Add Java QuickSort helper",
            commit_message="feat(sort): add QuickSort with JUnit tests",
            pr_title="Java QuickSort Implementation",
            pr_body="Adds quicksort algorithm with assertions",
            files=[
                ProposedFile(
                    path="src/main/java/QuickSort.java",
                    change_type="CREATE",
                    content="package dsa;\npublic class QuickSort { public static void sort(int[] a){} }"
                )
            ]
        )
        res = ValidationEngine.validate(proposal, allowed_paths=["src/"])
        self.assertTrue(res.is_valid)

class PipelineExecutionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="developer@example.com", password="password123")
        self.connection = GitHubConnection.objects.create(
            user=self.user,
            github_user_id="12345",
            github_username="testdev",
            installation_id="demo-install-123"
        )
        self.connection.set_access_token("demo-token")
        self.connection.save()

        self.repo = Repository.objects.create(
            connection=self.connection,
            github_repo_id="999",
            full_name="testdev/java-practice",
            default_branch="main",
            allowed_paths=["src/"]
        )

        self.automation = Automation.objects.create(
            user=self.user,
            repository=self.repo,
            title="Daily DSA Java Practice",
            instructions="Practice Java algorithms daily",
            branch_strategy="PULL_REQUEST",
            require_approval=False,
            enabled=True
        )

    def test_rejection_without_ai_config(self):
        slot = "2026-10-13-no-ai-slot"
        result_msg = execute_automation_task(str(self.automation.id), slot)
        self.assertIn("AI Provider not configured", result_msg)
        execution = Execution.objects.get(automation=self.automation, scheduled_slot=slot)
        self.assertEqual(execution.status, "REJECTED")

    def test_automation_execution_pipeline_with_ai(self):
        from unittest.mock import patch, MagicMock
        ai_config = AIProviderConfig.objects.create(
            user=self.user,
            provider="openai",
            model_name="gpt-4o-mini"
        )
        ai_config.set_api_key("sk-test-key-mocked")
        ai_config.save()
        self.automation.ai_config = ai_config
        self.automation.save()

        mock_proposal = CodeProposal(
            summary="Java BST Practice",
            commit_message="feat(dsa): implement BST insertion with tests",
            pr_title="Java BST Insertion",
            pr_body="Adds BST algorithm with unit tests",
            files=[
                ProposedFile(
                    path="src/main/java/BSTNode.java",
                    change_type="CREATE",
                    content="package dsa;\npublic class BSTNode { public int val; public BSTNode(int v){ this.val = v; } }"
                ),
                ProposedFile(
                    path="src/test/java/BSTNodeTest.java",
                    change_type="CREATE",
                    content="package dsa;\nimport org.junit.jupiter.api.Test;\npublic class BSTNodeTest { @Test public void test(){ new BSTNode(1); } }"
                )
            ]
        )

        with patch('apps.ai_engine.adapters.openai_adapter.OpenAIAdapter.generate_changes', return_value=mock_proposal):
            slot = "2026-10-13-test-slot"
            result_msg = execute_automation_task(str(self.automation.id), slot)
            self.assertIn("published successfully", result_msg)

            execution = Execution.objects.get(automation=self.automation, scheduled_slot=slot)
            self.assertEqual(execution.status, "SUCCESS")
            self.assertTrue(execution.published_change is not None)
            self.assertTrue(execution.generated_files.count() > 0)
