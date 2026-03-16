from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.providers.azure_openai_adapter import AzureOpenAIAdapter
from app.providers.google_adapter import GoogleAdapter
from app.providers.openai_adapter import OpenAIAdapter
from app.providers.structured_extraction import (
    MAX_EXTRACTION_OUTPUT_TOKENS,
    SYSTEM_PROMPT,
    _azure_openai_extract,
    _compose_prompt_text,
    _google_extract,
    _normalize_extraction,
    _ollama_extract,
    _openai_extract,
    extract_with_llm_detailed,
)


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://example.test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=request, response=response)

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, responses, calls):
        self._responses = responses
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        self._calls.append({"url": url, "headers": headers, "json": json})
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


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
            document_template="pdd",
            processing_profile="balanced",
            use_full_media=False,
        )
    except RuntimeError as exc:
        assert "stage=structured_extraction" in str(exc)
        assert "AZURE_OPENAI_CHAT_DEPLOYMENT" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing chat deployment")
    get_settings.cache_clear()


def test_compose_prompt_text_includes_template_hint_and_context_notes():
    prompt = _compose_prompt_text(
        "Transcript body",
        document_template="custom_sop",
        context_notes="This is a GAFTA contract compliance process.",
    )
    assert "Document template hint:" in prompt
    assert "automation opportunities" in prompt
    assert "Additional context provided by user:" in prompt
    assert "GAFTA contract compliance process" in prompt
    assert "Source transcript:" in prompt


def test_compose_prompt_text_can_prepend_system_prompt():
    prompt = _compose_prompt_text(
        "Transcript body",
        document_template="pdd",
        context_notes=None,
        include_system_prompt=True,
    )
    assert "Invariant extraction policy:" in prompt
    assert SYSTEM_PROMPT in prompt


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


def test_normalize_extraction_dedupes_effort_and_sipoc_and_aligns_step_titles():
    normalized = _normalize_extraction(
        {
            "process_steps": [
                {"step_no": 1, "title": "Complaint Intake", "summary": "Receive complaint"},
                {"step_no": 2, "title": "Complaint Assignment", "summary": "Assign complaint"},
            ],
            "effort_data": [
                {"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10},
                {"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10},
                {"step_no": 2, "effort_minutes_min": 2, "effort_minutes_max": 5},
            ],
            "sipoc": [
                {
                    "supplier": "Customer",
                    "input": "Complaint",
                    "process_step": "complaint intake",
                    "output": "Complaint record",
                    "customer": "Complaint Analyst",
                },
                {
                    "supplier": "Customer",
                    "input": "Complaint",
                    "process_step": "Complaint Intake",
                    "output": "Complaint record",
                    "customer": "Complaint Analyst",
                },
                {
                    "supplier": "Complaint Analyst",
                    "input": "Categorized complaint",
                    "process_step": "Complaint Assignment",
                    "output": "Assigned complaint",
                    "customer": "Resolution Team",
                },
            ],
        }
    )
    assert normalized["effort_data"] == [
        {"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10},
        {"step_no": 2, "effort_minutes_min": 2, "effort_minutes_max": 5},
    ]
    assert normalized["sipoc"] == [
        {
            "supplier": "Customer",
            "input": "Complaint",
            "process_step": "Complaint Intake",
            "output": "Complaint record",
            "customer": "Complaint Analyst",
        },
        {
            "supplier": "Complaint Analyst",
            "input": "Categorized complaint",
            "process_step": "Complaint Assignment",
            "output": "Assigned complaint",
            "customer": "Resolution Team",
        },
    ]


@pytest.mark.parametrize(
    ("extractor", "kwargs", "token_path", "prompt_path"),
    [
        (
            _openai_extract,
            {"api_key": "test-key", "model": "gpt-4.1"},
            ("max_completion_tokens",),
            ("messages", 0, "content"),
        ),
        (
            _azure_openai_extract,
            {
                "api_key": "test-key",
                "deployment": "chat-deployment",
                "endpoint": "https://example.openai.azure.com",
            },
            ("max_completion_tokens",),
            ("messages", 0, "content"),
        ),
        (
            _google_extract,
            {"api_key": "test-key", "model": "gemini-2.5-pro"},
            ("generationConfig", "maxOutputTokens"),
            ("contents", 0, "parts", 0, "text"),
        ),
        (
            _ollama_extract,
            {"model": "llama3.2", "base_url": "http://127.0.0.1:11434"},
            ("options", "num_predict"),
            ("prompt",),
        ),
    ],
)
def test_extraction_requests_include_token_caps_and_prompt_policy(monkeypatch, extractor, kwargs, token_path, prompt_path):
    calls = []
    responses = [
        _FakeResponse(
            {"choices": [{"message": {"content": "{\"process_steps\":[{\"summary\":\"Do work\"}],\"confidence\":0.8}"}}]}
            if extractor is _openai_extract
            else {"choices": [{"message": {"content": "{\"process_steps\":[{\"summary\":\"Do work\"}],\"confidence\":0.8}"}}]}
            if extractor is _azure_openai_extract
            else {"candidates": [{"content": {"parts": [{"text": "{\"process_steps\":[{\"summary\":\"Do work\"}],\"confidence\":0.8}"}]}}]}
            if extractor is _google_extract
            else {"response": "{\"process_steps\":[{\"summary\":\"Do work\"}],\"confidence\":0.8}"}
        )
    ]
    monkeypatch.setattr(
        "app.providers.structured_extraction.httpx.Client",
        lambda *args, **kwargs_: _FakeClient(responses, calls),
    )

    result = extractor(
        transcript_text="Transcript body",
        document_template="custom_sop",
        context_notes="Context note",
        frame_images=[],
        **kwargs,
    )

    assert result is not None
    body = calls[0]["json"]
    token_value = body
    for key in token_path:
        token_value = token_value[key]
    assert token_value == MAX_EXTRACTION_OUTPUT_TOKENS

    prompt_value = body
    for key in prompt_path:
        prompt_value = prompt_value[key]
    if extractor in {_openai_extract, _azure_openai_extract}:
        assert prompt_value == SYSTEM_PROMPT
        user_content = body["messages"][1]["content"][0]["text"]
        assert "Document template hint:" in user_content
        assert "Additional context provided by user:" in user_content
    else:
        assert SYSTEM_PROMPT in prompt_value
        assert "Document template hint:" in prompt_value
        assert "Additional context provided by user:" in prompt_value
    assert "Do not split adjacent activities into separate steps" in str(body)
    assert "Add an effort_data row for every process step" in str(body)
    assert "Create one SIPOC row per process step" in str(body)


def test_openai_extract_retries_transient_failures(monkeypatch):
    calls = []
    sleeps = []
    responses = [
        _FakeResponse({}, status_code=429),
        _FakeResponse({}, status_code=503),
        _FakeResponse({"choices": [{"message": {"content": "{\"process_steps\":[{\"summary\":\"Recovered\"}],\"confidence\":0.8}"}}]}),
    ]
    monkeypatch.setattr(
        "app.providers.structured_extraction.httpx.Client",
        lambda *args, **kwargs: _FakeClient(responses, calls),
    )
    monkeypatch.setattr("app.providers.structured_extraction.time.sleep", lambda seconds: sleeps.append(seconds))

    result = _openai_extract(
        transcript_text="Transcript body",
        document_template="pdd",
        context_notes=None,
        api_key="test-key",
        model="gpt-4.1",
        frame_images=[],
    )

    assert result is not None
    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_openai_extract_does_not_retry_non_transient_failures(monkeypatch):
    calls = []
    sleeps = []
    responses = [_FakeResponse({}, status_code=401)]
    monkeypatch.setattr(
        "app.providers.structured_extraction.httpx.Client",
        lambda *args, **kwargs: _FakeClient(responses, calls),
    )
    monkeypatch.setattr("app.providers.structured_extraction.time.sleep", lambda seconds: sleeps.append(seconds))

    with pytest.raises(httpx.HTTPStatusError):
        _openai_extract(
            transcript_text="Transcript body",
            document_template="pdd",
            context_notes=None,
            api_key="test-key",
            model="gpt-4.1",
            frame_images=[],
        )

    assert len(calls) == 1
    assert sleeps == []


def test_extract_with_llm_detailed_returns_error_for_invalid_json(monkeypatch):
    calls = []
    responses = [{"choices": [{"message": {"content": "not json"}}]}]
    monkeypatch.setattr(
        "app.providers.structured_extraction.httpx.Client",
        lambda *args, **kwargs: _FakeClient([_FakeResponse(responses[0])], calls),
    )

    result, error = extract_with_llm_detailed(
        provider="openai",
        transcript_text="Transcript body",
        document_template="pdd",
        context_notes=None,
        api_key="test-key",
        model="gpt-4.1",
        frame_images=[],
    )

    assert result is None
    assert error == "Structured extraction returned no valid JSON. Raw preview: not json"
