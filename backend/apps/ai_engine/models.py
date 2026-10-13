import uuid
from django.db import models
from django.conf import settings
from apps.common.encryption import encrypt_secret, decrypt_secret, mask_secret

class AIProviderConfig(models.Model):
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('gemini', 'Google Gemini'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_configs')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default='openai')
    model_name = models.CharField(max_length=100, default='gpt-4o-mini')
    encrypted_api_key = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def set_api_key(self, api_key: str):
        self.encrypted_api_key = encrypt_secret(api_key)

    def get_api_key(self) -> str:
        return decrypt_secret(self.encrypted_api_key)

    @property
    def masked_api_key(self) -> str:
        raw = self.get_api_key()
        return mask_secret(raw)

    def __str__(self):
        return f"{self.get_provider_display()} ({self.model_name}) - {self.user.email}"
