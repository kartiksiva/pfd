from pathlib import Path

from app.providers.google_adapter import GoogleAdapter
from app.providers.openai_adapter import OpenAIAdapter


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

    text = adapter.transcribe({"transcript": None, "audio": None, "video": {"storage_key": str(video), "content_type": "video/mp4"}})
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

    text = adapter.transcribe({"transcript": None, "audio": {"storage_key": str(audio), "content_type": "audio/wav"}, "video": None})
    assert called["ok"] is True
    assert text == "openai media transcript"
