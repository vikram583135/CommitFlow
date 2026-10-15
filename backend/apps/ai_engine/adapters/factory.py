from apps.ai_engine.models import AIProviderConfig
from .base import BaseAIAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter

def get_ai_adapter(config: AIProviderConfig) -> BaseAIAdapter:
    api_key = config.get_api_key()
    provider = config.provider.lower()
    model = config.model_name

    if provider == 'openai':
        return OpenAIAdapter(api_key=api_key, model_name=model)
    elif provider == 'anthropic':
        return AnthropicAdapter(api_key=api_key, model_name=model)
    elif provider == 'gemini':
        # Can fallback to OpenAI-compatible or google-genai
        return OpenAIAdapter(api_key=api_key, model_name=model)
    else:
        raise ValueError(f"Unsupported AI provider: {provider}")
