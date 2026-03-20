import asyncio
from io import BytesIO

from starlette.datastructures import UploadFile

from app.pipelines.media_understanding import build_media_understanding_payload
from app.pipelines.document_generation import generate_document_from_extraction
from app.pipelines.process_extraction import extract_process_structure
from app.providers.base import read_transcript_file
from app.transcript_utils import normalize_transcript_text, read_transcript_asset
from app.upload_validation import ValidationError, validate_and_persist_inputs


SAMPLE_VTT = """WEBVTT

1
00:00:00.000 --> 00:00:05.000
Priya Nair: A complaint can come in through email,
web form, customer support portal,
or occasionally by phone.

2
00:00:05.000 --> 00:00:09.000
Daniel Brooks: Approximately how many complaints do you receive each day?
"""


def test_normalize_transcript_text_converts_webvtt_to_clean_utterances():
    asset = normalize_transcript_text(SAMPLE_VTT, filename="meeting.vtt", content_type="text/vtt")
    assert asset.format == "webvtt"
    assert asset.text == (
        "Priya Nair: A complaint can come in through email, web form, customer support portal, or occasionally by phone.\n"
        "Daniel Brooks: Approximately how many complaints do you receive each day?"
    )
    assert "WEBVTT" not in asset.text
    assert "-->" not in asset.text


def test_normalize_transcript_text_handles_webvtt_without_speaker_labels():
    asset = normalize_transcript_text(
        "WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\nOpen the intake mailbox\n\n2\n00:00:02.000 --> 00:00:04.000\nReview the new complaints",
        filename="plain.txt",
        content_type="text/plain",
    )
    assert asset.format == "webvtt"
    assert asset.text == "Open the intake mailbox\nReview the new complaints"


def test_normalize_transcript_text_leaves_plain_text_unchanged():
    asset = normalize_transcript_text("Step one\nStep two", filename="flow.txt", content_type="text/plain")
    assert asset.format is None
    assert asset.text == "Step one\nStep two"


def test_validate_and_persist_inputs_accepts_webvtt_upload(tmp_path):
    upload = UploadFile(filename="teams-export.vtt", file=BytesIO(SAMPLE_VTT.encode("utf-8")), headers={"content-type": "text/vtt"})
    manifest = asyncio.run(
        validate_and_persist_inputs(
            job_id="job-vtt",
            uploads_dir=tmp_path,
            video_file=None,
            audio_file=None,
            transcript_file=upload,
        )
    )
    assert manifest["transcript"]["content_type"] == "text/vtt"
    asset = read_transcript_asset(manifest)
    assert asset is not None
    assert asset.format == "webvtt"
    assert "Priya Nair:" in asset.text
    assert "-->" not in asset.text


def test_validate_and_persist_inputs_rejects_unsupported_transcript_mime(tmp_path):
    upload = UploadFile(filename="notes.rtf", file=BytesIO(b"{\\rtf1}"), headers={"content-type": "application/rtf"})
    try:
        asyncio.run(
            validate_and_persist_inputs(
                job_id="job-bad-mime",
                uploads_dir=tmp_path,
                video_file=None,
                audio_file=None,
                transcript_file=upload,
            )
        )
    except ValidationError as exc:
        assert exc.code == "ERR_UNSUPPORTED_MIME"
    else:
        raise AssertionError("Expected ValidationError for unsupported transcript MIME type")


def test_read_transcript_file_normalizes_webvtt_from_manifest(tmp_path):
    transcript = tmp_path / "meeting.vtt"
    transcript.write_text(SAMPLE_VTT, encoding="utf-8")
    text = read_transcript_file(
        {
            "transcript": {
                "filename": "meeting.vtt",
                "content_type": "text/vtt",
                "storage_key": str(transcript),
            }
        }
    )
    assert text is not None
    assert "Priya Nair:" in text
    assert "WEBVTT" not in text
    assert "-->" not in text


def test_raw_webvtt_noise_is_not_promoted_to_process_steps():
    media_payload = build_media_understanding_payload(
        {
            "transcript_text": "WEBVTT\n\n1\n00:00:00.000 --> 00:00:04.000\nA complaint is logged\n\n2\n00:00:04.000 --> 00:00:08.000\nComplaint is validated",
            "transcript_format": "webvtt",
            "visual_events": [],
            "process_candidates": [],
            "confidence": 0.6,
        }
    )
    extraction = extract_process_structure(media_payload)
    summaries = [step["summary"] for step in extraction["process_steps"]]
    assert summaries == ["A complaint is logged", "Complaint is validated"]
    joined = " ".join(summaries)
    assert "WEBVTT" not in joined
    assert "-->" not in joined
    assert "00:00:00.000" not in joined


def test_webvtt_derived_frequency_does_not_capture_full_transcript_blob():
    media_payload = build_media_understanding_payload(
        {
            "transcript_text": "\n".join(
                [
                    "Daniel Brooks: Thanks, everyone. The goal today is to understand the process.",
                    "Priya Nair: A complaint can come in through email, web form, customer support portal, or occasionally by phone.",
                    "Anita Rao: Around 180 to 220 per day on average. Mondays are usually higher, and after product releases we can see spikes.",
                    "Priya Nair: Analysts manually assign the complaint to one of three resolution teams: billing operations, product support, or field service.",
                ]
            ),
            "transcript_format": "webvtt",
            "visual_events": [],
            "process_candidates": [
                {"source": "transcript", "summary": "Complaint Intake and Record Creation", "confidence": 0.8},
                {"source": "transcript", "summary": "Assignment to Resolution Team", "confidence": 0.8},
            ],
            "confidence": 0.8,
        }
    )
    extraction = extract_process_structure(media_payload)
    sop = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    frequency = sop["prerequisites_and_inputs"]["input_documents_data"][0]["frequency"]
    assert frequency.startswith("Daily (Around 180 to 220 per day on average")
    assert "Thanks, everyone." not in frequency
    assert "Analysts manually assign" not in frequency
