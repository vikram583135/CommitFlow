import uuid
from django.db import models
from django.conf import settings
from apps.common.encryption import encrypt_secret, decrypt_secret

class GitHubConnection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='github_connections')
    github_user_id = models.CharField(max_length=100)
    github_username = models.CharField(max_length=255)
    installation_id = models.CharField(max_length=100, blank=True)
    encrypted_access_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def set_access_token(self, token: str):
        self.encrypted_access_token = encrypt_secret(token)

    def get_access_token(self) -> str:
        return decrypt_secret(self.encrypted_access_token)

    def __str__(self):
        return f"{self.github_username} (User: {self.user.email})"

class Repository(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    connection = models.ForeignKey(GitHubConnection, on_delete=models.CASCADE, related_name='repositories')
    github_repo_id = models.CharField(max_length=100)
    full_name = models.CharField(max_length=255, db_index=True)
    default_branch = models.CharField(max_length=100, default='main')
    allowed_paths = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name']
        unique_together = ('connection', 'github_repo_id')

    def __str__(self):
        return self.full_name
