from rest_framework import serializers
from .models import Automation
from apps.github_integration.serializers import RepositorySerializer
from apps.ai_engine.serializers import AIProviderConfigSerializer

class AutomationSerializer(serializers.ModelSerializer):
    repository_details = RepositorySerializer(source='repository', read_only=True)
    ai_config_details = AIProviderConfigSerializer(source='ai_config', read_only=True)

    class Meta:
        model = Automation
        fields = [
            'id', 'title', 'task_type', 'instructions', 'repository',
            'repository_details', 'ai_config', 'ai_config_details',
            'cron_expression', 'timezone', 'branch_strategy',
            'require_approval', 'max_files', 'enabled',
            'last_run_at', 'next_run_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_run_at', 'next_run_at', 'created_at', 'updated_at']
