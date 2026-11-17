from rest_framework import serializers
from .models import Automation
from apps.github_integration.serializers import RepositorySerializer
from apps.ai_engine.serializers import AIProviderConfigSerializer
from apps.ai_engine.models import AIProviderConfig
from apps.github_integration.models import Repository
from apps.validation.validator import validate_allowed_paths
from .scheduling import next_scheduled_at

class AutomationSerializer(serializers.ModelSerializer):
    repository_details = RepositorySerializer(source='repository', read_only=True)
    ai_config_details = AIProviderConfigSerializer(source='ai_config', read_only=True)
    allowed_paths = serializers.ListField(child=serializers.CharField(), write_only=True, required=False)
    instructions = serializers.CharField(max_length=20000)
    require_approval = serializers.BooleanField(default=True)
    enabled = serializers.BooleanField(default=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = getattr(self.context.get('request'), 'user', None)
        self.fields['repository'].queryset = Repository.objects.filter(
            connection__user=user, connection__is_active=True, is_active=True) if user and user.is_authenticated else Repository.objects.none()
        self.fields['ai_config'].queryset = AIProviderConfig.objects.filter(
            user=user, is_active=True) if user and user.is_authenticated else AIProviderConfig.objects.none()

    def validate(self, attrs):
        previous = self.instance
        try:
            next_scheduled_at(attrs.get('cron_expression', previous.cron_expression if previous else '0 9 * * *'),
                           attrs.get('timezone', previous.timezone if previous else 'UTC'))
            repo = attrs.get('repository', previous.repository if previous else None)
            paths = attrs.get('allowed_paths', repo.allowed_paths if repo else [])
            validate_allowed_paths(paths)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        if not 1 <= attrs.get('max_files', previous.max_files if previous else 3) <= 10:
            raise serializers.ValidationError({'max_files': 'Choose between 1 and 10 files.'})
        strategy = attrs.get('branch_strategy', previous.branch_strategy if previous else 'PULL_REQUEST')
        approval = attrs.get('require_approval', previous.require_approval if previous else True)
        if strategy == 'DIRECT_PUSH' and not approval:
            raise serializers.ValidationError('Direct pushes require manual approval.')
        return attrs

    def create(self, validated_data):
        from django.db import transaction
        paths = validated_data.pop('allowed_paths', None)
        with transaction.atomic():
            if paths is not None:
                repo = validated_data['repository']
                repo.allowed_paths = validate_allowed_paths(paths)
                repo.save(update_fields=['allowed_paths'])
            return super().create(validated_data)

    def update(self, instance, validated_data):
        from django.db import transaction
        paths = validated_data.pop('allowed_paths', None)
        with transaction.atomic():
            if paths is not None:
                repo = validated_data.get('repository', instance.repository)
                repo.allowed_paths = validate_allowed_paths(paths)
                repo.save(update_fields=['allowed_paths'])
            return super().update(instance, validated_data)

    class Meta:
        model = Automation
        fields = [
            'id', 'title', 'task_type', 'instructions', 'repository',
            'repository_details', 'ai_config', 'ai_config_details', 'allowed_paths',
            'cron_expression', 'timezone', 'branch_strategy',
            'require_approval', 'max_files', 'enabled',
            'last_run_at', 'next_run_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_run_at', 'next_run_at', 'created_at', 'updated_at']
