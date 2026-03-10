from pathlib import Path

from app.pipelines.frame_selector import select_key_frames
from app.pipelines.media_understanding import build_media_understanding_payload


def test_frame_selector_returns_empty_without_video():
    frames = select_key_frames(
        input_manifest={"video": None, "audio": None, "transcript": None},
        evidence={"transcript_text": "step one", "visual_events": [], "process_candidates": []},
    )
    assert frames == []


def test_frame_selector_applies_visual_and_video_rules(tmp_path: Path):
    fake_video = tmp_path / "demo.mov"
    fake_video.write_bytes(b"video-bytes")
    frames = select_key_frames(
        input_manifest={"video": {"storage_key": str(fake_video)}},
        evidence={
            "transcript_text": "00:05 Start process\n00:20 Submit form",
            "visual_events": [{"event": "ui_context_shift", "timestamp_seconds": 20, "confidence": 0.8}],
            "process_candidates": [{"source": "video", "action": "segment_process_frames", "timestamp_seconds": 30}],
        },
        max_frames=20,
        baseline_interval_seconds=15,
    )
    assert len(frames) >= 4
    reasons = {row["reason"] for row in frames}
    assert "baseline" in reasons
    assert "scene_change" in reasons
    assert "process_hotspot" in reasons
    assert "transcript_anchor" in reasons


def test_media_payload_includes_key_frames(tmp_path: Path):
    fake_video = tmp_path / "demo.mov"
    fake_video.write_bytes(b"video-bytes")
    payload = build_media_understanding_payload(
        {
            "transcript_text": "Start process\nValidate request\nComplete process",
            "visual_events": [{"event": "screen_transition", "confidence": 0.7}],
            "process_candidates": [{"source": "video", "action": "segment_process_frames"}],
            "structured_extraction": None,
        },
        input_manifest={"video": {"storage_key": str(fake_video)}, "audio": None, "transcript": None},
    )
    assert "key_frames" in payload
    assert isinstance(payload["key_frames"], list)
    assert payload["key_frames"]
