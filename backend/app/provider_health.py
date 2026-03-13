from dataclasses import dataclass
import io
import time
from typing import Any, Dict, List, Optional, Tuple
import wave

import httpx

from app.config import get_settings


@dataclass
class ProviderHealthResult:
    provider: str
    ok: bool
    latency_ms: Optional[int]
    status_code: Optional[int]
    message: str
    details: Optional[Dict[str, Any]] = None


def _normalize_azure_mode(mode: Optional[str]) -> str:
    normalized = str(mode or "auto").strip().lower()
    return normalized if normalized in {"openai_v1", "deployment", "auto"} else "auto"


def _azure_mode_candidates(mode: Optional[str]) -> list[str]:
    normalized = _normalize_azure_mode(mode)
    if normalized == "openai_v1":
        return ["openai_v1"]
    if normalized == "deployment":
        return ["deployment"]
    return ["openai_v1", "deployment"]


def _azure_headers(api_key: str, mode: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"} if mode == "openai_v1" else {"api-key": api_key}


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


def _check_azure_openai(
    api_key: Optional[str],
    endpoint: Optional[str],
    chat_deployment: Optional[str],
    transcription_deployment: Optional[str],
    api_version: str,
    mode: str,
    timeout_seconds: float = 10.0,
) -> ProviderHealthResult:
    if not api_key or not endpoint:
        return ProviderHealthResult(
            provider="azure_openai",
            ok=False,
            latency_ms=None,
            status_code=None,
            message="AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT is not configured.",
        )

    base = endpoint.rstrip("/")
    requested_mode = _normalize_azure_mode(mode)

    def _check_chat_deployment(
        deployment: Optional[str], selected_mode: str
    ) -> Tuple[bool, Optional[int], Optional[int], str]:
        if not deployment:
            return False, None, None, "chat: deployment_not_configured"
        if selected_mode == "openai_v1":
            url = f"{base}/openai/v1/chat/completions"
        else:
            url = f"{base}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        headers = _azure_headers(api_key, selected_mode)
        body = {
            "model": deployment,
            "messages": [{"role": "user", "content": "ping"}],
            "max_completion_tokens": 16,
        }
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, headers=headers, json=body)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if response.status_code == 200:
                return True, elapsed_ms, response.status_code, f"chat:{selected_mode}:available"
            return False, elapsed_ms, response.status_code, f"chat:{selected_mode}:status_{response.status_code}"
        except httpx.TimeoutException:
            return False, None, None, f"chat:{selected_mode}:timeout"
        except httpx.HTTPError as exc:
            return False, None, None, f"chat:{selected_mode}:request_failed_{exc.__class__.__name__}"

    def _check_transcription_deployment(
        deployment: Optional[str], selected_mode: str
    ) -> Tuple[bool, Optional[int], Optional[int], str]:
        if not deployment:
            return False, None, None, "transcription: deployment_not_configured"
        if selected_mode == "openai_v1":
            url = f"{base}/openai/v1/audio/transcriptions"
            data = {"model": deployment, "language": "en", "response_format": "json"}
        else:
            url = f"{base}/openai/deployments/{deployment}/audio/transcriptions?api-version={api_version}"
            data = {"language": "en", "response_format": "json"}
        headers = _azure_headers(api_key, selected_mode)
        audio = io.BytesIO()
        with wave.open(audio, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 1600)
        audio.seek(0)
        files = {"file": ("healthcheck.wav", audio, "audio/wav")}
        start = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(url, headers=headers, data=data, files=files)
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if response.status_code == 200:
                return True, elapsed_ms, response.status_code, f"transcription:{selected_mode}:available"
            return (
                False,
                elapsed_ms,
                response.status_code,
                f"transcription:{selected_mode}:status_{response.status_code}",
            )
        except httpx.TimeoutException:
            return False, None, None, f"transcription:{selected_mode}:timeout"
        except httpx.HTTPError as exc:
            return False, None, None, f"transcription:{selected_mode}:request_failed_{exc.__class__.__name__}"

    chat_ok, chat_latency, chat_status, chat_msg, chat_mode_used = False, None, None, "", None
    tx_ok, tx_latency, tx_status, tx_msg, tx_mode_used = False, None, None, "", None

    for selected_mode in _azure_mode_candidates(requested_mode):
        chat_ok, chat_latency, chat_status, chat_msg = _check_chat_deployment(chat_deployment, selected_mode)
        if chat_ok:
            chat_mode_used = selected_mode
            break
    if not chat_ok and not chat_msg:
        chat_msg = "chat:unknown"

    for selected_mode in _azure_mode_candidates(requested_mode):
        tx_ok, tx_latency, tx_status, tx_msg = _check_transcription_deployment(transcription_deployment, selected_mode)
        if tx_ok:
            tx_mode_used = selected_mode
            break
    if not tx_ok and not tx_msg:
        tx_msg = "transcription:unknown"

    if requested_mode == "openai_v1":
        overall_ok = bool(chat_ok and tx_ok and (chat_mode_used in {None, "openai_v1"}) and (tx_mode_used in {None, "openai_v1"}))
    elif requested_mode == "deployment":
        overall_ok = bool(chat_ok and tx_ok and (chat_mode_used in {None, "deployment"}) and (tx_mode_used in {None, "deployment"}))
    else:
        overall_ok = chat_ok and tx_ok

    latency = int((chat_latency or 0) + (tx_latency or 0)) if (chat_latency is not None or tx_latency is not None) else None
    status_code = tx_status if tx_status and not tx_ok else chat_status
    details = {
        "requested_mode": requested_mode,
        "chat_ok": chat_ok,
        "chat_mode_used": chat_mode_used,
        "chat_status_code": chat_status,
        "chat_message": chat_msg,
        "transcription_ok": tx_ok,
        "transcription_mode_used": tx_mode_used,
        "transcription_status_code": tx_status,
        "transcription_message": tx_msg,
    }
    return ProviderHealthResult(
        provider="azure_openai",
        ok=overall_ok,
        latency_ms=latency,
        status_code=status_code,
        message=f"Azure deployment check: {chat_msg}; {tx_msg}.",
        details=details,
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
        _check_azure_openai(
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            chat_deployment=settings.azure_openai_chat_deployment,
            transcription_deployment=settings.azure_openai_transcription_deployment,
            api_version=settings.azure_openai_api_version,
            mode=settings.azure_openai_mode,
            timeout_seconds=timeout_seconds,
        ),
        _check_google(api_key=settings.google_api_key, timeout_seconds=timeout_seconds),
        _check_ollama(base_url=settings.ollama_base_url, timeout_seconds=timeout_seconds),
    ]
