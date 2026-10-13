from rest_framework import serializers
from .models import Execution, GeneratedFile, PublishedChange

class GeneratedFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeneratedFile
        fields = ['id', 'file_path', 'change_type', 'original_content', 'new_content', 'diff_patch']

class PublishedChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublishedChange
        fields = ['id', 'branch_name', 'commit_sha', 'commit_message', 'pull_request_url', 'pull_request_number', 'published_at']

class ExecutionSerializer(serializers.ModelSerializer):
    generated_files = GeneratedFileSerializer(many=True, read_only=True)
    published_change = PublishedChangeSerializer(read_only=True)
    automation_title = serializers.CharField(source='automation.title', read_only=True)
    repository_name = serializers.CharField(source='automation.repository.full_name', read_only=True)

    class Meta:
        model = Execution
        fields = [
            'id', 'automation', 'automation_title', 'repository_name',
            'status', 'scheduled_slot', 'idempotency_key', 'attempt_number',
            'input_tokens', 'output_tokens', 'validation_results',
            'error_message', 'started_at', 'completed_at',
            'generated_files', 'published_change'
        ]
        read_only_fields = ['id', 'started_at', 'completed_at']
