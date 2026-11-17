import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True, null=True)
    auth_provider = models.CharField(
        max_length=20,
        choices=[('email', 'Email'), ('github', 'GitHub'), ('google', 'Google')],
        default='email'
    )
    provider_id = models.CharField(max_length=255, blank=True, db_index=True)
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.email


class OAuthAttempt(models.Model):
    state_hash = models.CharField(max_length=64, primary_key=True)
    provider = models.CharField(max_length=20)
    redirect_uri = models.URLField()
    code_challenge = models.CharField(max_length=43)
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)


class SocialIdentity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_identities')
    provider = models.CharField(max_length=20)
    subject = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'subject'], name='unique_social_subject'),
            models.UniqueConstraint(fields=['user', 'provider'], name='unique_user_provider'),
        ]
