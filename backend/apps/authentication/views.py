import base64
import hashlib
import hmac
import re
import secrets
from smtplib import SMTPException
from datetime import timedelta
from urllib.parse import urlencode
import httpx
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework import serializers
from rest_framework.exceptions import ValidationError as APIValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.authtoken.models import Token
from rest_framework.authentication import SessionAuthentication
from .token_auth import ExpiringTokenAuthentication
from .models import User, OAuthAttempt, SocialIdentity
from .serializers import UserSerializer, RegisterSerializer, LoginSerializer
from .oauth import OAuthService
from apps.github_integration.models import GitHubConnection


def user_token(user):
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        token, _ = Token.objects.get_or_create(user=user)
        if timezone.now() - token.created > timedelta(seconds=settings.API_TOKEN_TTL):
            token.delete()
            token = Token.objects.create(user=user)
    return token


class AuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method == 'POST' and not isinstance(request.data, dict):
            raise APIValidationError('A JSON object is required.')


class RegisterView(AuthView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError:
            return Response({'error': 'An account with this email already exists.'}, status=400)
        ticket = signing.dumps({'user': str(user.pk), 'email': user.email}, salt='verify-email')
        link = settings.FRONTEND_URL + '/auth/callback?' + urlencode({'verify': ticket})
        try:
            send_mail('Verify your CommitFlow email', 'Verify your email: ' + link,
                      settings.DEFAULT_FROM_EMAIL, [user.email])
        except (SMTPException, OSError):
            return Response({'error': 'Account created, but email delivery failed. Resend verification when email service is available.'}, status=503)
        return Response({'message': 'Check your email to verify your account.', 'verification_required': True},
                        status=status.HTTP_201_CREATED)


class ResendVerificationView(AuthView):
    throttle_scope = 'email'

    def post(self, request):
        user = User.objects.filter(email__iexact=str(request.data.get('email', '')), is_active=True,
                                   email_verified=False).first()
        if user:
            ticket = signing.dumps({'user': str(user.pk), 'email': user.email}, salt='verify-email')
            link = settings.FRONTEND_URL + '/auth/callback?' + urlencode({'verify': ticket})
            try:
                send_mail('Verify your CommitFlow email', 'Verify your email: ' + link,
                          settings.DEFAULT_FROM_EMAIL, [user.email])
            except (SMTPException, OSError):
                return Response({'error': 'Email delivery is temporarily unavailable.'}, status=503)
        return Response({'message': 'If an unverified account exists, a verification link has been sent.'})


class VerifyEmailView(AuthView):
    def post(self, request):
        try:
            data = signing.loads(request.data.get('ticket', ''), salt='verify-email', max_age=86400)
            changed = User.objects.filter(pk=data['user'], email=data['email'], email_verified=False,
                                          is_active=True).update(email_verified=True)
            if not changed:
                raise ValueError()
        except (signing.BadSignature, KeyError, ValueError, TypeError):
            return Response({'error': 'Verification link is invalid, expired, or already used.'}, status=400)
        return Response({'message': 'Email verified. You can sign in now.'})


class LoginView(AuthView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        if not user.email_verified:
            return Response({'error': 'Verify your email before signing in.'}, status=403)
        return Response({'token': user_token(user).key, 'user': UserSerializer(user).data})


class PasswordResetRequestView(AuthView):
    throttle_scope = 'email'
    def post(self, request):
        user = User.objects.filter(email__iexact=str(request.data.get('email', '')), is_active=True,
                                   email_verified=True).first()
        if user and user.has_usable_password():
            query = urlencode({'reset_user': str(user.pk), 'reset_token': default_token_generator.make_token(user)})
            try:
                send_mail('Reset your CommitFlow password', 'Reset your password: ' +
                          settings.FRONTEND_URL + '/auth/callback?' + query,
                          settings.DEFAULT_FROM_EMAIL, [user.email])
            except (SMTPException, OSError):
                return Response({'error': 'Email delivery is temporarily unavailable.'}, status=503)
        return Response({'message': 'If an eligible account exists, a reset link has been sent.'})


class PasswordResetConfirmView(AuthView):
    def post(self, request):
        payload = serializers.Serializer(data=request.data)
        payload.fields.update(user=serializers.UUIDField(), token=serializers.CharField(max_length=256),
                              password=serializers.CharField(min_length=8, max_length=128))
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=data['user'], is_active=True, email_verified=True)
                if not default_token_generator.check_token(user, data['token']):
                    raise ValueError()
                validate_password(data['password'], user)
                user.set_password(data['password'])
                user.save(update_fields=['password'])
                Token.objects.filter(user=user).delete()
        except ValidationError as exc:
            return Response({'error': exc.messages}, status=400)
        except (User.DoesNotExist, ValueError, TypeError, KeyError):
            return Response({'error': 'Reset link is invalid or expired.'}, status=400)
        return Response({'message': 'Password updated. Sign in with your new password.'})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Successfully logged out.'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class OAuthUrlView(AuthView):
    authentication_classes = [ExpiringTokenAuthentication, SessionAuthentication]
    def get(self, request):
        provider = str(request.query_params.get('provider', 'github')).lower()
        redirect_uri = request.query_params.get('redirect_uri', '')
        challenge = request.query_params.get('code_challenge', '')
        if redirect_uri != settings.FRONTEND_URL + '/auth/callback' or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge):
            return Response({'error': 'Invalid redirect URI or PKCE challenge.'}, status=400)
        try:
            state = secrets.token_urlsafe(32)
            data = OAuthService.get_auth_url(provider, redirect_uri, state, challenge)
            OAuthAttempt.objects.filter(expires_at__lt=timezone.now()).delete()
            OAuthAttempt.objects.create(state_hash=hashlib.sha256(state.encode()).hexdigest(), provider=provider,
                                        redirect_uri=redirect_uri, code_challenge=challenge,
                                        user=request.user if request.user.is_authenticated else None,
                                        expires_at=timezone.now() + timedelta(minutes=10))
            return Response(data)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)


class OAuthCallbackView(AuthView):
    authentication_classes = [ExpiringTokenAuthentication, SessionAuthentication]
    def post(self, request):
        state = request.data.get('state', '')
        verifier = request.data.get('code_verifier', '')
        code = request.data.get('code', '')
        if (not isinstance(code, str) or not code or len(code) > 2048 or not isinstance(state, str)
                or len(state) > 128 or not isinstance(verifier, str) or not re.fullmatch(r'[A-Za-z0-9_~.-]{43,128}', verifier)):
            return Response({'error': 'Invalid OAuth state or verifier.'}, status=400)
        state_hash = hashlib.sha256(state.encode()).hexdigest()
        attempt = OAuthAttempt.objects.filter(pk=state_hash, consumed=False, expires_at__gt=timezone.now()).first()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        if (not attempt or not hmac.compare_digest(attempt.code_challenge, challenge)
                or attempt.provider != request.data.get('provider')
                or attempt.redirect_uri != request.data.get('redirect_uri')
                or (attempt.user_id and (not request.user.is_authenticated or request.user.pk != attempt.user_id))):
            return Response({'error': 'OAuth attempt is invalid or expired. Start sign-in again.'}, status=400)
        if not OAuthAttempt.objects.filter(pk=state_hash, consumed=False).update(consumed=True):
            return Response({'error': 'OAuth attempt already used.'}, status=400)
        try:
            profile = OAuthService.exchange(attempt.provider, request.data.get('code', ''), attempt.redirect_uri, verifier)
            with transaction.atomic():
                identity = SocialIdentity.objects.select_related('user').filter(
                    provider=attempt.provider, subject=profile['provider_id']).first()
                if attempt.user_id:
                    user = attempt.user
                    if identity and identity.user_id != user.pk:
                        raise ValueError('This social account is already linked to another user.')
                elif identity:
                    user = identity.user
                else:
                    if User.objects.filter(email__iexact=profile['email']).exists():
                        raise ValueError('Sign in to your existing account first, then connect this provider.')
                    user = User.objects.create_user(email=profile['email'], name=profile.get('name', ''),
                                                    auth_provider=attempt.provider, provider_id=profile['provider_id'],
                                                    email_verified=True)
                if not user.is_active:
                    raise ValueError('This account is disabled.')
                User.objects.select_for_update().get(pk=user.pk)
                if not identity:
                    SocialIdentity.objects.create(user=user, provider=attempt.provider, subject=profile['provider_id'])
                user.avatar_url = profile.get('avatar_url') or user.avatar_url
                if profile['email'].casefold() == user.email.casefold():
                    user.email_verified = True
                user.save(update_fields=['avatar_url', 'email_verified'])
                if attempt.provider == 'github':
                    connection, _ = GitHubConnection.objects.get_or_create(
                        user=user, github_user_id=profile['provider_id'], installation_id='oauth_user_account',
                        defaults={'github_username': profile['login']})
                    connection.github_username = profile['login']
                    connection.is_active = True
                    connection.set_access_token(profile['access_token'])
                    connection.save()
                token = user_token(user)
            return Response({'token': token.key, 'user': UserSerializer(user).data})
        except ValueError as exc:
            return Response({'error': str(exc)}, status=400)
        except (httpx.HTTPError, IntegrityError, KeyError, TypeError):
            return Response({'error': 'OAuth exchange failed. Start sign-in again.'}, status=400)
