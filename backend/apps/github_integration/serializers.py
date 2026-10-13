from rest_framework import serializers
from .models import GitHubConnection, Repository

class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = [
            'id', 'github_repo_id', 'full_name', 'default_branch',
            'allowed_paths', 'is_active', 'last_synced_at', 'created_at'
        ]
        read_only_fields = ['id', 'github_repo_id', 'created_at']

class GitHubConnectionSerializer(serializers.ModelSerializer):
    repositories = RepositorySerializer(many=True, read_only=True)

    class Meta:
        model = GitHubConnection
        fields = [
            'id', 'github_user_id', 'github_username',
            'installation_id', 'created_at', 'repositories'
        ]
        read_only_fields = ['id', 'created_at']
