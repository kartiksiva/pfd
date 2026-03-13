from app.provider_health import _check_azure_openai


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = ""
        self.headers = {}


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None, data=None, files=None):
        if not self._responses:
            raise RuntimeError("missing_fake_response")
        return self._responses.pop(0)


def test_azure_health_reports_chat_and_transcription_independently(monkeypatch):
    # chat fails (500), transcription succeeds (200) in openai_v1 mode.
    responses = [_FakeResponse(500), _FakeResponse(200)]
    monkeypatch.setattr(
        "app.provider_health.httpx.Client",
        lambda timeout: _FakeClient(responses),
    )

    result = _check_azure_openai(
        api_key="k",
        endpoint="https://example.cognitiveservices.azure.com",
        chat_deployment="gpt-4o",
        transcription_deployment="gpt-4o-transcribe",
        api_version="2024-02-01",
        mode="openai_v1",
        timeout_seconds=1.0,
    )

    assert result.ok is False
    assert result.details is not None
    assert result.details["chat_ok"] is False
    assert result.details["transcription_ok"] is True
    assert result.details["requested_mode"] == "openai_v1"


def test_azure_health_auto_mode_falls_back_to_deployment(monkeypatch):
    # openai_v1 chat/tx fail, deployment chat/tx succeed.
    responses = [
        _FakeResponse(401),  # chat openai_v1
        _FakeResponse(200),  # chat deployment
        _FakeResponse(401),  # tx openai_v1
        _FakeResponse(200),  # tx deployment
    ]
    monkeypatch.setattr(
        "app.provider_health.httpx.Client",
        lambda timeout: _FakeClient(responses),
    )

    result = _check_azure_openai(
        api_key="k",
        endpoint="https://example.cognitiveservices.azure.com",
        chat_deployment="gpt-4o",
        transcription_deployment="gpt-4o-transcribe",
        api_version="2024-02-01",
        mode="auto",
        timeout_seconds=1.0,
    )

    assert result.ok is True
    assert result.details is not None
    assert result.details["chat_mode_used"] == "deployment"
    assert result.details["transcription_mode_used"] == "deployment"
