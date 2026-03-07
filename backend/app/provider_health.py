from dataclasses import dataclass
import time
from typing import List, Optional

import httpx

from app.config import get_settings


@dataclass
class ProviderHealthResult:
    provider: str
    ok: bool
    latency_ms: Optional[int]
    status_code: Optional[int]
    message: str


def _check_openai(api_key: Optional[str], timeout_seconds: float = 10.0) -> ProviderHealthResult:
    if not api_key:
        return ProviderHealthResult(
            provider="openai",
            ok=False,
            latency_ms=None,
            status_code=None,
            message="OPENAI_API_KEY is not configured.",
        )

    url = "https://api.openai.com/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"}

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url, headers=headers)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        ok = response.status_code == 200
        msg = "OpenAI API reachable." if ok else f"OpenAI API returned status {response.status_code}."
        return ProviderHealthResult(
            provider="openai",
            ok=ok,
            latency_ms=elapsed_ms,
            status_code=response.status_code,
            message=msg,
        )
    except httpx.TimeoutException:
        return ProviderHealthResult(
            provider="openai",
            ok=False,
            latency_ms=None,
            status_code=None,
            message="OpenAI API request timed out.",
        )
    except httpx.HTTPError as exc:
        return ProviderHealthResult(
            provider="openai",
            ok=False,
            latency_ms=None,
            status_code=None,
            message=f"OpenAI API request failed: {exc.__class__.__name__}.",
        )


def _check_google(api_key: Optional[str], timeout_seconds: float = 10.0) -> ProviderHealthResult:
    if not api_key:
        return ProviderHealthResult(
            provider="google",
            ok=False,
            latency_ms=None,
            status_code=None,
            message="GOOGLE_API_KEY is not configured.",
        )

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        ok = response.status_code == 200
        msg = "Google API reachable." if ok else f"Google API returned status {response.status_code}."
        return ProviderHealthResult(
            provider="google",
            ok=ok,
            latency_ms=elapsed_ms,
            status_code=response.status_code,
            message=msg,
        )
    except httpx.TimeoutException:
        return ProviderHealthResult(
            provider="google",
            ok=False,
            latency_ms=None,
            status_code=None,
            message="Google API request timed out.",
        )
    except httpx.HTTPError as exc:
        return ProviderHealthResult(
            provider="google",
            ok=False,
            latency_ms=None,
            status_code=None,
            message=f"Google API request failed: {exc.__class__.__name__}.",
        )


def _check_ollama(base_url: str, timeout_seconds: float = 10.0) -> ProviderHealthResult:
    url = f"{base_url.rstrip('/')}/api/tags"
    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.get(url)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        ok = response.status_code == 200
        msg = "Ollama API reachable." if ok else f"Ollama API returned status {response.status_code}."
        return ProviderHealthResult(
            provider="ollama",
            ok=ok,
            latency_ms=elapsed_ms,
            status_code=response.status_code,
            message=msg,
        )
    except httpx.TimeoutException:
        return ProviderHealthResult(
            provider="ollama",
            ok=False,
            latency_ms=None,
            status_code=None,
            message="Ollama API request timed out.",
        )
    except httpx.HTTPError as exc:
        return ProviderHealthResult(
            provider="ollama",
            ok=False,
            latency_ms=None,
            status_code=None,
            message=f"Ollama API request failed: {exc.__class__.__name__}.",
        )


def check_providers_health(timeout_seconds: float = 10.0) -> List[ProviderHealthResult]:
    settings = get_settings()
    return [
        _check_openai(api_key=settings.openai_api_key, timeout_seconds=timeout_seconds),
        _check_google(api_key=settings.google_api_key, timeout_seconds=timeout_seconds),
        _check_ollama(base_url=settings.ollama_base_url, timeout_seconds=timeout_seconds),
    ]
