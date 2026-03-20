from app.pipelines.transcript_media_consistency import (
    should_check_transcript_media_consistency,
    verify_transcript_media_consistency,
)


def _manifest(with_media: bool = True, with_transcript: bool = True):
    return {
        "video": {"storage_key": "/tmp/demo.mov"} if with_media else None,
        "audio": None,
        "transcript": {"storage_key": "/tmp/demo.vtt"} if with_transcript else None,
    }


def test_should_check_transcript_media_consistency_requires_media_and_transcript():
    assert should_check_transcript_media_consistency(_manifest(True, True), "A" * 250) is True
    assert should_check_transcript_media_consistency(_manifest(False, True), "A" * 250) is False
    assert should_check_transcript_media_consistency(_manifest(True, False), "A" * 250) is False
    assert should_check_transcript_media_consistency(_manifest(True, True), "short") is False


def test_verify_transcript_media_consistency_detects_match(monkeypatch):
    monkeypatch.setattr(
        "app.pipelines.transcript_media_consistency._verification_transcript",
        lambda provider, input_manifest: (
            "Speaker 1: Customer submits complaint and analyst validates complaint in CRM. " * 6
        ),
    )
    monkeypatch.setattr("app.pipelines.transcript_media_consistency._similarity_score", lambda left, right: 0.9)
    result = verify_transcript_media_consistency(
        provider="openai",
        input_manifest=_manifest(True, True),
        transcript_text="WEBVTT\n\n1\n00:00:00.000 --> 00:00:05.000\n"
        + ("Customer submits complaint and analyst validates complaint in CRM. " * 6),
    )
    assert result["checked"] is True
    assert result["verdict"] == "match"
    assert result["similarity_score"] is not None


def test_verify_transcript_media_consistency_detects_suspected_mismatch(monkeypatch):
    monkeypatch.setattr(
        "app.pipelines.transcript_media_consistency._verification_transcript",
        lambda provider, input_manifest: "Invoice approver reviews purchase order and posts entry to ERP.",
    )
    monkeypatch.setattr("app.pipelines.transcript_media_consistency._similarity_score", lambda left, right: 0.1)
    result = verify_transcript_media_consistency(
        provider="google",
        input_manifest=_manifest(True, True),
        transcript_text="Customer complaint is received, validated, categorized, and assigned to a resolution team." * 5,
    )
    assert result["checked"] is True
    assert result["verdict"] == "suspected_mismatch"


def test_verify_transcript_media_consistency_returns_inconclusive_on_transcription_failure(monkeypatch):
    def _raise(provider, input_manifest):
        raise RuntimeError("network error")

    monkeypatch.setattr("app.pipelines.transcript_media_consistency._verification_transcript", _raise)
    result = verify_transcript_media_consistency(
        provider="azure_openai",
        input_manifest=_manifest(True, True),
        transcript_text="Customer complaint is received and validated in CRM." * 10,
    )
    assert result["checked"] is True
    assert result["verdict"] == "inconclusive"
    assert "verification_transcription_failed" in result["reasons"][0]


def test_verify_transcript_media_consistency_marks_ollama_unsupported():
    result = verify_transcript_media_consistency(
        provider="ollama",
        input_manifest=_manifest(True, True),
        transcript_text="Customer complaint is received and validated in CRM." * 10,
    )
    assert result["checked"] is False
    assert result["verdict"] == "unsupported"
