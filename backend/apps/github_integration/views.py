from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import GitHubConnection, Repository
from .serializers import GitHubConnectionSerializer, RepositorySerializer
from .services import GitHubAppService

class GitHubConnectionListView(generics.ListCreateAPIView):
    serializer_class = GitHubConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubConnection.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class GitHubConnectionDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = GitHubConnectionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GitHubConnection.objects.filter(user=self.request.user)

class RepositoryListView(generics.ListAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Repository.objects.filter(connection__user=self.request.user)

class RepositoryDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Repository.objects.filter(connection__user=self.request.user)

class RepositorySyncView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Synchronizes authorized repositories directly from GitHub API.
        """
        repos = GitHubAppService.sync_user_repositories(request.user)
        return Response(RepositorySerializer(repos, many=True).data)

class GitHubOAuthCallbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        installation_id = request.data.get('installation_id')
        code = request.data.get('code')

        connection, _ = GitHubConnection.objects.get_or_create(
            user=request.user,
            defaults={
                'github_user_id': request.data.get('github_user_id', 'gh_user'),
                'github_username': request.data.get('github_username', request.user.name or 'developer'),
                'installation_id': installation_id or 'user_connection',
            }
        )
        if installation_id:
            connection.installation_id = installation_id
            connection.save(update_fields=['installation_id'])

        # Auto-sync repositories upon connecting
        GitHubAppService.sync_user_repositories(request.user)

        return Response(GitHubConnectionSerializer(connection).data)

class GitHubWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        signature = request.headers.get("X-Hub-Signature-256", "")
        # In production, verify signature
        if signature and not GitHubAppService.verify_webhook_signature(request.body, signature):
            return Response({"error": "Invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        event = request.headers.get("X-GitHub-Event", "ping")
        payload = request.data

        if event == "installation":
            action = payload.get("action")
            installation = payload.get("installation", {})
            inst_id = str(installation.get("id"))
            if action == "deleted":
                GitHubConnection.objects.filter(installation_id=inst_id).delete()

        return Response({"status": "received", "event": event})
