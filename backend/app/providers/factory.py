from app.providers.base import ProviderAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.openai_adapter import OpenAIAdapter


def get_provider_adapter(provider: str) -> ProviderAdapter:
    if provider == "openai":
        return OpenAIAdapter()
    return GoogleAdapter()

