from app.providers.base import ProviderAdapter
from app.providers.azure_openai_adapter import AzureOpenAIAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.ollama_adapter import OllamaAdapter
from app.providers.openai_adapter import OpenAIAdapter


def get_provider_adapter(provider: str) -> ProviderAdapter:
    if provider == "openai":
        return OpenAIAdapter()
    if provider == "azure_openai":
        return AzureOpenAIAdapter()
    if provider == "ollama":
        return OllamaAdapter()
    return GoogleAdapter()
