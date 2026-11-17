from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        if not user.email_verified:
            raise AuthenticationFailed('Verify your email before signing in.')
        if timezone.now() - token.created > timedelta(seconds=settings.API_TOKEN_TTL):
            raise AuthenticationFailed('Session expired. Please sign in again.')
        return user, token
