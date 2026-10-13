from rest_framework import serializers
from .models import AIProviderConfig

class AIProviderConfigSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(write_only=True, required=False)
    masked_api_key = serializers.CharField(read_only=True)

    class Meta:
        model = AIProviderConfig
        fields = [
            'id', 'provider', 'model_name', 'api_key',
            'masked_api_key', 'is_active', 'created_at'
        ]
        read_only_fields = ['id', 'masked_api_key', 'created_at']

    def create(self, validated_data):
        api_key = validated_data.pop('api_key', '')
        config = AIProviderConfig(**validated_data)
        if api_key:
            config.set_api_key(api_key)
        config.save()
        return config

    def update(self, instance, validated_data):
        api_key = validated_data.pop('api_key', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if api_key:
            instance.set_api_key(api_key)
        instance.save()
        return instance
