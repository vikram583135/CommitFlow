import uuid
from django.db import models
from apps.automations.models import Automation

class Execution(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('AWAITING_APPROVAL', 'Awaiting User Approval'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REJECTED', 'Rejected by Validation'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    automation = models.ForeignKey(Automation, on_delete=models.CASCADE, related_name='executions')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    scheduled_slot = models.CharField(max_length=100, db_index=True)
    idempotency_key = models.CharField(max_length=255, blank=True)
    attempt_number = models.IntegerField(default=1)
    
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    validation_results = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        unique_together = ('automation', 'scheduled_slot')

    def __str__(self):
        return f"Run {self.id} [{self.status}] - {self.automation.title} ({self.scheduled_slot})"

class GeneratedFile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(Execution, on_delete=models.CASCADE, related_name='generated_files')
    file_path = models.CharField(max_length=500)
    change_type = models.CharField(max_length=50, default='CREATE')
    original_content = models.TextField(blank=True)
    new_content = models.TextField()
    diff_patch = models.TextField(blank=True)

    class Meta:
        ordering = ['file_path']

    def __str__(self):
        return f"{self.change_type} {self.file_path}"

class PublishedChange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.OneToOneField(Execution, on_delete=models.CASCADE, related_name='published_change')
    branch_name = models.CharField(max_length=255)
    commit_sha = models.CharField(max_length=100)
    commit_message = models.TextField()
    pull_request_url = models.URLField(blank=True, null=True)
    pull_request_number = models.IntegerField(null=True, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Commit {self.commit_sha[:7]} ({self.branch_name})"
