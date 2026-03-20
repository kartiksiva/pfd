from app.providers.azure_openai_adapter import AzureOpenAIAdapter
from app.providers.factory import get_provider_adapter
from app.providers.google_adapter import GoogleAdapter


def test_factory_resolves_azure_openai_adapter():
    adapter = get_provider_adapter("azure_openai")
    assert isinstance(adapter, AzureOpenAIAdapter)


def test_factory_defaults_to_google_for_unknown_provider():
    adapter = get_provider_adapter("unknown")
    assert isinstance(adapter, GoogleAdapter)
