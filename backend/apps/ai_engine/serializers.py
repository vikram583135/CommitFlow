from rest_framework import serializers
from .models import AIProviderConfig
from django.db import transaction
from apps.authentication.models import User

class AIProviderConfigSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False, max_length=1024)
    masked_api_key = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(default=True)

    class Meta:
        model = AIProviderConfig
        fields = [
            'id', 'provider', 'model_name', 'api_key',
            'masked_api_key', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'masked_api_key', 'created_at']

    def validate(self, attrs):
        if not self.instance and not attrs.get('api_key'):
            raise serializers.ValidationError({'api_key': 'An API key is required.'})
        return attrs

    def create(self, validated_data):
        api_key = validated_data.pop('api_key', '')
        config = AIProviderConfig(**validated_data)
        if api_key:
            config.set_api_key(api_key)
        with transaction.atomic():
            User.objects.select_for_update().get(pk=config.user_id)
            config.save()
            if config.is_active:
                AIProviderConfig.objects.filter(user=config.user).exclude(pk=config.pk).update(is_active=False)
        return config

    def update(self, instance, validated_data):
        api_key = validated_data.pop('api_key', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if api_key:
            instance.set_api_key(api_key)
        with transaction.atomic():
            User.objects.select_for_update().get(pk=instance.user_id)
            instance.save()
            if instance.is_active:
                AIProviderConfig.objects.filter(user=instance.user).exclude(pk=instance.pk).update(is_active=False)
        return instance
