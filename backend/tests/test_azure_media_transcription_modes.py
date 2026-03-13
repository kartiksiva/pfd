from pathlib import Path
from typing import Optional

import pytest

from app.providers.media_transcription import transcribe_with_azure_openai


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Optional[dict] = None,
        text: str = "",
        content_type: str = "application/json",
    ):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {"content-type": content_type}

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse], calls: list[dict]):
        self._responses = responses
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, data=None, files=None):
        self._calls.append({"url": url, "headers": headers or {}, "data": data or {}})
        if not self._responses:
            raise RuntimeError("missing_fake_response")
        return self._responses.pop(0)


def _manifest_with_audio(tmp_path: Path, filename: str = "clip.wav", size_bytes: int = 8) -> dict:
    audio = tmp_path / filename
    audio.write_bytes(b"x" * size_bytes)
    return {
        "audio": {
            "storage_key": str(audio),
            "filename": filename,
            "content_type": "audio/wav",
        },
        "video": None,
        "transcript": None,
    }


def test_azure_transcription_openai_v1_mode(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    responses = [_FakeResponse(status_code=200, payload={"text": "hello from azure"})]
    monkeypatch.setattr(
        "app.providers.media_transcription.httpx.Client",
        lambda timeout: _FakeClient(responses, calls),
    )
    manifest = _manifest_with_audio(tmp_path)

    text = transcribe_with_azure_openai(
        input_manifest=manifest,
        api_key="test-key",
        endpoint="https://example.cognitiveservices.azure.com",
        deployment="gpt-4o-transcribe",
        api_version="2024-02-01",
        mode="openai_v1",
    )

    assert "hello from azure" in text
    assert calls[0]["url"].endswith("/openai/v1/audio/transcriptions")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"


def test_azure_transcription_deployment_mode(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    responses = [_FakeResponse(status_code=200, payload={"text": "deployment mode transcript"})]
    monkeypatch.setattr(
        "app.providers.media_transcription.httpx.Client",
        lambda timeout: _FakeClient(responses, calls),
    )
    manifest = _manifest_with_audio(tmp_path)

    text = transcribe_with_azure_openai(
        input_manifest=manifest,
        api_key="test-key",
        endpoint="https://example.cognitiveservices.azure.com",
        deployment="gpt-4o-transcribe",
        api_version="2024-02-01",
        mode="deployment",
    )

    assert "deployment mode transcript" in text
    assert (
        calls[0]["url"]
        == "https://example.cognitiveservices.azure.com/openai/deployments/gpt-4o-transcribe/audio/transcriptions?api-version=2024-02-01"
    )
    assert calls[0]["headers"]["api-key"] == "test-key"
    assert "model" not in calls[0]["data"]


def test_azure_transcription_auto_mode_falls_back(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    responses = [
        _FakeResponse(status_code=401, text="unauthorized"),
        _FakeResponse(status_code=200, payload={"text": "fallback succeeded"}),
    ]
    monkeypatch.setattr(
        "app.providers.media_transcription.httpx.Client",
        lambda timeout: _FakeClient(responses, calls),
    )
    manifest = _manifest_with_audio(tmp_path)

    text = transcribe_with_azure_openai(
        input_manifest=manifest,
        api_key="test-key",
        endpoint="https://example.cognitiveservices.azure.com",
        deployment="gpt-4o-transcribe",
        api_version="2024-02-01",
        mode="auto",
    )

    assert "fallback succeeded" in text
    assert len(calls) == 2
    assert calls[0]["url"].endswith("/openai/v1/audio/transcriptions")
    assert "/openai/deployments/gpt-4o-transcribe/audio/transcriptions" in calls[1]["url"]


def test_azure_transcription_auto_mode_returns_combined_error(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    responses = [
        _FakeResponse(status_code=401, text="unauthorized"),
        _FakeResponse(status_code=404, text="deployment not found"),
    ]
    monkeypatch.setattr(
        "app.providers.media_transcription.httpx.Client",
        lambda timeout: _FakeClient(responses, calls),
    )
    manifest = _manifest_with_audio(tmp_path)

    with pytest.raises(RuntimeError) as exc:
        transcribe_with_azure_openai(
            input_manifest=manifest,
            api_key="test-key",
            endpoint="https://example.cognitiveservices.azure.com",
            deployment="gpt-4o-transcribe",
            api_version="2024-02-01",
            mode="auto",
        )

    msg = str(exc.value)
    assert "azure_openai_transcription_failed" in msg
    assert "openai_v1" in msg
    assert "deployment" in msg


def test_azure_transcription_rejects_files_over_provider_limit(monkeypatch, tmp_path: Path):
    calls: list[dict] = []
    responses: list[_FakeResponse] = []
    monkeypatch.setattr(
        "app.providers.media_transcription.httpx.Client",
        lambda timeout: _FakeClient(responses, calls),
    )
    large = tmp_path / "large.wav"
    large.write_bytes(b"x")
    large.touch()
    with large.open("ab") as f:
        f.truncate((25 * 1024 * 1024) + 1)

    manifest = {
        "audio": {"storage_key": str(large), "filename": "large.wav", "content_type": "audio/wav"},
        "video": None,
        "transcript": None,
    }
    with pytest.raises(RuntimeError) as exc:
        transcribe_with_azure_openai(
            input_manifest=manifest,
            api_key="test-key",
            endpoint="https://example.cognitiveservices.azure.com",
            deployment="gpt-4o-transcribe",
            api_version="2024-02-01",
            mode="openai_v1",
        )
    assert "provider_file_too_large" in str(exc.value)
    assert calls == []
