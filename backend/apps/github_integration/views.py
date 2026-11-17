import hashlib
from django.db import transaction
from django.core.exceptions import ValidationError
from rest_framework import generics, status
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import GitHubConnection, Repository, WebhookDelivery
from .serializers import GitHubConnectionSerializer, RepositorySerializer
from .services import GitHubAppService, GitHubAPIError


def deactivate_connections(connections):
    from apps.automations.models import Automation
    ids = list(connections.values_list('pk', flat=True))
    connections.update(is_active=False, encrypted_access_token='')
    Repository.objects.filter(connection_id__in=ids).update(is_active=False)
    for automation in Automation.objects.filter(repository__connection_id__in=ids):
        automation.enabled = False
        automation.save(update_fields=['enabled'])


class GitHubConnectionListView(generics.ListAPIView):
    serializer_class = GitHubConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubConnection.objects.filter(user=self.request.user).prefetch_related('repositories')


class GitHubConnectionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = GitHubConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubConnection.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        deactivate_connections(GitHubConnection.objects.filter(pk=instance.pk))


class RepositoryListView(generics.ListAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Repository.objects.filter(connection__user=self.request.user, connection__is_active=True, is_active=True)


class RepositoryDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Repository.objects.filter(connection__user=self.request.user)


class RepositorySyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            repos = GitHubAppService.sync_user_repositories(request.user)
            return Response(RepositorySerializer(repos, many=True).data)
        except GitHubAPIError as exc:
            return Response({'error': str(exc)}, status=502)


class GitHubOAuthCallbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = serializers.Serializer(data=request.data)
        payload.fields.update(connection_id=serializers.UUIDField(), installation_id=serializers.RegexField(r'^[1-9][0-9]{0,19}$'))
        payload.is_valid(raise_exception=True)
        try:
            source = GitHubConnection.objects.get(pk=payload.validated_data['connection_id'], user=request.user,
                                                 is_active=True, installation_id='oauth_user_account')
            installation_id = payload.validated_data['installation_id']
            GitHubAppService.verify_installation_access(source, installation_id)
            with transaction.atomic():
                from apps.authentication.models import User
                User.objects.select_for_update().get(pk=request.user.pk)
                connection, _ = GitHubConnection.objects.get_or_create(user=request.user, installation_id=installation_id,
                    defaults={'github_user_id': source.github_user_id, 'github_username': source.github_username})
                connection.is_active = True
                connection.save(update_fields=['is_active'])
            return Response(GitHubConnectionSerializer(connection).data)
        except (GitHubConnection.DoesNotExist, ValueError, ValidationError):
            return Response({'error': 'A verified GitHub user connection is required.'}, status=400)
        except GitHubAPIError as exc:
            return Response({'error': str(exc)}, status=403)


class GitHubWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        body = request.body
        signature = request.headers.get('X-Hub-Signature-256', '')
        if not GitHubAppService.verify_webhook_signature(body, signature):
            return Response({'error': 'Missing or invalid signature'}, status=403)
        payload = request.data
        if not isinstance(payload, dict):
            return Response({'error': 'Invalid payload.'}, status=400)
        with transaction.atomic():
            _, created = WebhookDelivery.objects.get_or_create(body_hash=hashlib.sha256(body).hexdigest())
            if not created:
                return Response({'status': 'already received'})
            if request.headers.get('X-GitHub-Event') == 'installation':
                installation = payload.get('installation') or {}
                if payload.get('action') in ('deleted', 'suspend') and isinstance(installation, dict) and installation.get('id'):
                    deactivate_connections(GitHubConnection.objects.filter(installation_id=str(installation['id'])))
        return Response({'status': 'received'})
