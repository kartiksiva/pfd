from pathlib import Path

from app.config import get_settings
from app.providers.azure_openai_adapter import AzureOpenAIAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.structured_extraction import _compose_prompt_text, _normalize_extraction


def test_google_adapter_prefers_existing_transcript(tmp_path: Path):
    transcript = tmp_path / "input.txt"
    transcript.write_text("already provided transcript", encoding="utf-8")
    adapter = GoogleAdapter()

    text = adapter.transcribe(
        {
            "transcript": {"storage_key": str(transcript)},
            "audio": {"storage_key": str(tmp_path / "audio.mp3"), "content_type": "audio/mpeg"},
            "video": None,
        }
    )
    assert text == "already provided transcript"


def test_google_adapter_uses_media_transcriber(monkeypatch, tmp_path: Path):
    called = {"ok": False}

    def fake_transcribe(*, input_manifest, api_key, model):
        called["ok"] = True
        assert input_manifest["video"]["storage_key"].endswith("clip.mp4")
        assert model == "gemini-2.5-flash"
        return "google media transcript"

    monkeypatch.setattr("app.providers.google_adapter.transcribe_with_google", fake_transcribe)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake")
    adapter = GoogleAdapter()

    text = adapter.transcribe(
        {"transcript": None, "audio": None, "video": {"storage_key": str(video), "content_type": "video/mp4"}},
        use_full_media=True,
    )
    assert called["ok"] is True
    assert text == "google media transcript"


def test_openai_adapter_uses_media_transcriber(monkeypatch, tmp_path: Path):
    called = {"ok": False}

    def fake_transcribe(*, input_manifest, api_key, model):
        called["ok"] = True
        assert input_manifest["audio"]["storage_key"].endswith("call.wav")
        assert model == "gpt-4o-mini-transcribe"
        return "openai media transcript"

    monkeypatch.setattr("app.providers.openai_adapter.transcribe_with_openai", fake_transcribe)
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake")
    adapter = OpenAIAdapter()

    text = adapter.transcribe(
        {"transcript": None, "audio": {"storage_key": str(audio), "content_type": "audio/wav"}, "video": None},
        use_full_media=True,
    )
    assert called["ok"] is True
    assert text == "openai media transcript"


def test_azure_openai_adapter_uses_media_transcriber(monkeypatch, tmp_path: Path):
    called = {"ok": False}

    def fake_transcribe(*, input_manifest, api_key, endpoint, deployment, api_version, mode):
        called["ok"] = True
        assert input_manifest["audio"]["storage_key"].endswith("call.wav")
        assert deployment == "transcribe-deployment"
        assert endpoint == "https://example.openai.azure.com"
        assert api_version == "2024-10-21"
        assert mode == "auto"
        return "azure media transcript"

    monkeypatch.setattr("app.providers.azure_openai_adapter.transcribe_with_azure_openai", fake_transcribe)
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT", "transcribe-deployment")
    get_settings.cache_clear()
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake")
    adapter = AzureOpenAIAdapter()

    text = adapter.transcribe(
        {"transcript": None, "audio": {"storage_key": str(audio), "content_type": "audio/wav"}, "video": None},
        use_full_media=True,
    )
    assert called["ok"] is True
    assert text == "azure media transcript"
    get_settings.cache_clear()


def test_azure_openai_adapter_requires_transcription_deployment(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT", "")
    get_settings.cache_clear()
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"fake")
    adapter = AzureOpenAIAdapter()

    try:
        adapter.transcribe(
            {"transcript": None, "audio": {"storage_key": str(audio), "content_type": "audio/wav"}, "video": None},
            use_full_media=True,
        )
    except RuntimeError as exc:
        assert "stage=transcription" in str(exc)
        assert "AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing transcription deployment")
    get_settings.cache_clear()


def test_azure_openai_adapter_requires_chat_deployment_for_structured_extraction(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
    monkeypatch.setenv("LLM_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr("app.providers.azure_openai_adapter.select_key_frames", lambda **_kwargs: [])
    monkeypatch.setattr("app.providers.azure_openai_adapter.extract_key_frame_images", lambda **_kwargs: [])
    adapter = AzureOpenAIAdapter()

    try:
        adapter.build_evidence(
            input_manifest={"transcript": None, "audio": None, "video": None},
            transcript_text="hello world",
            processing_profile="balanced",
            use_full_media=False,
        )
    except RuntimeError as exc:
        assert "stage=structured_extraction" in str(exc)
        assert "AZURE_OPENAI_CHAT_DEPLOYMENT" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing chat deployment")
    get_settings.cache_clear()


def test_compose_prompt_text_includes_context_notes():
    prompt = _compose_prompt_text("Transcript body", "This is a GAFTA contract compliance process.")
    assert "Additional context provided by user:" in prompt
    assert "GAFTA contract compliance process" in prompt
    assert "Source transcript:" in prompt


def test_normalize_extraction_preserves_new_structured_fields():
    normalized = _normalize_extraction(
        {
            "process_name": "Sample",
            "process_steps": [{"step_no": 1, "summary": "Do work"}],
            "decision_rules": [{"condition": "data is missing", "action": "request update", "applies_to_step": 1}],
            "effort_data": [{"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10}],
            "pain_points": [{"description": "Manual rework", "quantification": "20 percent rework", "automation_signal": "high"}],
        }
    )
    assert normalized["decision_rules"][0]["condition"] == "data is missing"
    assert normalized["effort_data"][0]["effort_minutes_min"] == 8
    assert normalized["pain_points"][0]["automation_signal"] == "high"
