import uuid
from django.db import models
from django.conf import settings
from apps.github_integration.models import Repository
from apps.ai_engine.models import AIProviderConfig

class Automation(models.Model):
    TASK_TYPE_CHOICES = [
        ('coding_practice', 'Daily Coding Practice'),
        ('documentation', 'Documentation & Guides'),
        ('unit_tests', 'Unit Tests & Coverage'),
        ('learning_notes', 'Learning Notes & TIL'),
    ]

    BRANCH_STRATEGY_CHOICES = [
        ('PULL_REQUEST', 'Create Pull Request (Recommended)'),
        ('DIRECT_PUSH', 'Push Directly to Branch'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='automations')
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='automations')
    ai_config = models.ForeignKey(AIProviderConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name='automations')
    
    title = models.CharField(max_length=255)
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES, default='coding_practice')
    instructions = models.TextField(help_text="Detailed guidance for daily generation")
    cron_expression = models.CharField(max_length=50, default='0 9 * * *')
    timezone = models.CharField(max_length=50, default='UTC')
    
    branch_strategy = models.CharField(max_length=50, choices=BRANCH_STRATEGY_CHOICES, default='PULL_REQUEST')
    require_approval = models.BooleanField(default=False)
    max_files = models.IntegerField(default=3)
    enabled = models.BooleanField(default=True)
    
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.repository.full_name})"
