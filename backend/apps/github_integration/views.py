from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import GitHubConnection, Repository
from .serializers import GitHubConnectionSerializer, RepositorySerializer

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

class GitHubOAuthCallbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Receives GitHub OAuth code or installation details from frontend redirect.
        """
        code = request.data.get('code')
        installation_id = request.data.get('installation_id')
        
        # In a real environment, exchanges code with GitHub OAuth API
        # For local development/testing, supports linking installation
        connection, _ = GitHubConnection.objects.get_or_create(
            user=request.user,
            defaults={
                'github_user_id': request.data.get('github_user_id', 'gh-user-demo'),
                'github_username': request.data.get('github_username', 'demo-developer'),
                'installation_id': installation_id or 'demo-installation-id',
            }
        )
        if installation_id:
            connection.installation_id = installation_id
            connection.save()
            
        return Response(GitHubConnectionSerializer(connection).data)
