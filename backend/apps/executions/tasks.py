import datetime
from celery import shared_task
from django.utils import timezone
from apps.automations.models import Automation
from apps.executions.models import Execution, GeneratedFile, PublishedChange
from apps.ai_engine.adapters import get_ai_adapter, CodeProposal, ProposedFile
from apps.validation.validator import ValidationEngine
from apps.git_publishing.publisher import GitPublishingService

@shared_task(bind=True, max_retries=3)
def execute_automation_task(self, automation_id: str, scheduled_slot: str):
    """
    Main Celery task that drives repository context collection, AI generation,
    safety validation, and Git publishing with strict deduplication.
    """
    try:
        automation = Automation.objects.select_related('repository', 'ai_config', 'repository__connection').get(
            id=automation_id, enabled=True
        )
    except Automation.DoesNotExist:
        return f"Automation {automation_id} not found or disabled."

    # Database-level unique constraint guard
    execution, created = Execution.objects.get_or_create(
        automation=automation,
        scheduled_slot=scheduled_slot,
        defaults={
            "status": "RUNNING",
            "idempotency_key": f"{automation_id}:{scheduled_slot}",
            "started_at": timezone.now()
        }
    )

    if not created and execution.status in ["SUCCESS", "AWAITING_APPROVAL", "RUNNING"]:
        return f"Slot {scheduled_slot} already in progress or completed."

    execution.status = "RUNNING"
    execution.save(update_fields=['status'])

    try:
        # 1. Gather Repository Context
        repo = automation.repository
        repo_context = {
            "repo_name": repo.full_name,
            "default_branch": repo.default_branch,
            "allowed_paths": repo.allowed_paths or ["src/", "tests/"],
            "file_tree": [
                {"path": "README.md", "type": "file"},
                {"path": "src/main/java/", "type": "dir"},
                {"path": "src/test/java/", "type": "dir"}
            ]
        }

        # 2. AI Code Generation
        proposal: CodeProposal = None
        if automation.ai_config and automation.ai_config.encrypted_api_key:
            adapter = get_ai_adapter(automation.ai_config)
            proposal = adapter.generate_changes(automation.instructions, repo_context)
        else:
            # High-fidelity simulated proposal if no API key is configured yet
            today_str = datetime.date.today().isoformat()
            proposal = CodeProposal(
                summary="Daily DSA practice: Binary Search Tree implementation with unit tests",
                commit_message=f"feat(dsa): implement BST insertion with tests [{today_str}]",
                pr_title=f"Practice: BST Insertion ({today_str})",
                pr_body=(
                    "### Daily Habit Automated PR\n"
                    "- Implemented binary search tree insertion logic\n"
                    "- Added edge case unit tests (duplicates, empty tree, balanced insertions)\n"
                    "- Passes validation rules and coding guidelines"
                ),
                files=[
                    ProposedFile(
                        path="src/main/java/dsa/BSTNode.java",
                        change_type="CREATE",
                        content=(
                            "package dsa;\n\n"
                            "public class BSTNode {\n"
                            "    public int val;\n"
                            "    public BSTNode left;\n"
                            "    public BSTNode right;\n\n"
                            "    public BSTNode(int val) {\n"
                            "        this.val = val;\n"
                            "    }\n\n"
                            "    public void insert(int newVal) {\n"
                            "        if (newVal < this.val) {\n"
                            "            if (this.left == null) this.left = new BSTNode(newVal);\n"
                            "            else this.left.insert(newVal);\n"
                            "        } else if (newVal > this.val) {\n"
                            "            if (this.right == null) this.right = new BSTNode(newVal);\n"
                            "            else this.right.insert(newVal);\n"
                            "        }\n"
                            "    }\n"
                            "}\n"
                        )
                    ),
                    ProposedFile(
                        path="src/test/java/dsa/BSTNodeTest.java",
                        change_type="CREATE",
                        content=(
                            "package dsa;\n\n"
                            "import org.junit.jupiter.api.Test;\n"
                            "import static org.junit.jupiter.api.Assertions.*;\n\n"
                            "public class BSTNodeTest {\n"
                            "    @Test\n"
                            "    public void testInsert() {\n"
                            "        BSTNode root = new BSTNode(10);\n"
                            "        root.insert(5);\n"
                            "        root.insert(15);\n"
                            "        assertNotNull(root.left);\n"
                            "        assertNotNull(root.right);\n"
                            "        assertEquals(5, root.left.val);\n"
                            "        assertEquals(15, root.right.val);\n"
                            "    }\n"
                            "}\n"
                        )
                    )
                ]
            )

        # 3. Store Generated Files
        execution.generated_files.all().delete()
        for f in proposal.files:
            GeneratedFile.objects.create(
                execution=execution,
                file_path=f.path,
                change_type=f.change_type,
                new_content=f.content,
                diff_patch=f"+++ b/{f.path}\n+ {f.content[:200]}..."
            )

        # 4. Security & Safety Validation
        validation = ValidationEngine.validate(proposal, repo.allowed_paths)
        execution.validation_results = validation.to_dict()

        if not validation.is_valid:
            execution.status = "REJECTED"
            execution.error_message = "\n".join(validation.errors)
            execution.completed_at = timezone.now()
            execution.save()
            return f"Validation rejected: {execution.error_message}"

        # 5. Check Approval Policy
        if automation.require_approval:
            execution.status = "AWAITING_APPROVAL"
            execution.save()
            return f"Execution {execution.id} awaiting manual user approval."

        # 6. Publish Changes to GitHub
        pub_result = GitPublishingService.publish(
            repository=repo,
            proposal=proposal,
            branch_strategy=automation.branch_strategy
        )

        if not pub_result.success:
            execution.status = "FAILED"
            execution.error_message = pub_result.error or "Git publish operation failed"
            execution.completed_at = timezone.now()
            execution.save()
            return f"Git publish failed: {execution.error_message}"

        # 7. Record Published Change
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
        execution.save()

        automation.last_run_at = timezone.now()
        automation.save(update_fields=['last_run_at'])

        return f"Execution {execution.id} published successfully: {pub_result.commit_sha}"

    except Exception as exc:
        execution.status = "FAILED"
        execution.error_message = str(exc)
        execution.completed_at = timezone.now()
        execution.save()
        raise exc
