from rest_framework import serializers
from .models import GitHubConnection, Repository
from apps.validation.validator import validate_allowed_paths

class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = [
            'id', 'github_repo_id', 'full_name', 'default_branch',
            'allowed_paths', 'is_active', 'last_synced_at', 'created_at'
        ]
        read_only_fields = ['id', 'github_repo_id', 'full_name', 'default_branch', 'last_synced_at', 'created_at']

    def validate_allowed_paths(self, value):
        try:
            return validate_allowed_paths(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))

class GitHubConnectionSerializer(serializers.ModelSerializer):
    repositories = RepositorySerializer(many=True, read_only=True)

    class Meta:
        model = GitHubConnection
        fields = [
            'id', 'github_user_id', 'github_username',
            'installation_id', 'is_active', 'created_at', 'repositories'
        ]
        read_only_fields = fields
