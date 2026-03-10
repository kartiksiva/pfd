import json
import re
import subprocess
from typing import Dict, List, Optional, Tuple


TIMESTAMP_PATTERN = re.compile(r"(?<!\d)(\d{1,2}):([0-5]\d)(?::([0-5]\d))?(?!\d)")


def _to_seconds(hh: int, mm: int, ss: int) -> int:
    return hh * 3600 + mm * 60 + ss


def _extract_timestamps_from_text(text: str) -> List[float]:
    if not text:
        return []
    values: List[float] = []
    for match in TIMESTAMP_PATTERN.finditer(text):
        p1 = int(match.group(1))
        p2 = int(match.group(2))
        p3 = match.group(3)
        if p3 is None:
            values.append(float(_to_seconds(0, p1, p2)))
        else:
            values.append(float(_to_seconds(p1, p2, int(p3))))
    return values


def _probe_duration_seconds(video_path: str) -> Optional[float]:
    if not video_path:
        return None
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        video_path,
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=8, check=True)
        payload = json.loads(result.stdout or "{}")
        duration = float((payload.get("format") or {}).get("duration") or 0.0)
        return duration if duration > 0 else None
    except Exception:
        return None


def _estimate_duration_seconds(transcript_text: str, process_candidates: List[Dict]) -> float:
    transcript_lines = len([line for line in transcript_text.splitlines() if line.strip()])
    candidate_count = len(process_candidates)
    estimate = max(transcript_lines * 5, candidate_count * 8, 60)
    return float(min(estimate, 3600))


def _frame_reason(event_name: str) -> str:
    name = (event_name or "").lower()
    if "transition" in name or "shift" in name:
        return "scene_change"
    if "error" in name:
        return "exception_state"
    if "submit" in name or "approval" in name:
        return "business_event"
    return "visual_event"


def _insert_frame(candidates: List[Tuple[float, str, float]], timestamp_seconds: float, reason: str, confidence: float) -> None:
    if timestamp_seconds < 0:
        return
    candidates.append((round(timestamp_seconds, 2), reason, round(max(min(confidence, 0.99), 0.3), 2)))


def _dedupe_and_limit(candidates: List[Tuple[float, str, float]], max_frames: int, min_gap_seconds: float) -> List[Dict]:
    # Sort by confidence desc first so dedupe keeps stronger candidates, then stable by time.
    ordered = sorted(candidates, key=lambda row: (-row[2], row[0]))
    selected: List[Tuple[float, str, float]] = []
    for row in ordered:
        if any(abs(row[0] - existing[0]) < min_gap_seconds for existing in selected):
            continue
        selected.append(row)
        if len(selected) >= max_frames:
            break
    selected.sort(key=lambda row: row[0])
    return [
        {"timestamp_seconds": ts, "reason": reason, "confidence": conf}
        for ts, reason, conf in selected
    ]


def select_key_frames(
    *,
    input_manifest: Optional[Dict],
    evidence: Dict,
    max_frames: int = 48,
    baseline_interval_seconds: float = 12.0,
    min_gap_seconds: float = 2.0,
) -> List[Dict]:
    manifest = input_manifest or {}
    video_entry = manifest.get("video") or {}
    if not video_entry:
        return []

    transcript_text = evidence.get("transcript_text", "") or ""
    process_candidates = evidence.get("process_candidates", []) or []
    visual_events = evidence.get("visual_events", []) or []

    duration = _probe_duration_seconds(str(video_entry.get("storage_key") or "")) or _estimate_duration_seconds(
        transcript_text=transcript_text,
        process_candidates=process_candidates,
    )

    frame_candidates: List[Tuple[float, str, float]] = []

    # Rule 1: baseline sampling for temporal coverage.
    cursor = 0.0
    while cursor < duration:
        _insert_frame(frame_candidates, cursor, "baseline", 0.5)
        cursor += baseline_interval_seconds
    _insert_frame(frame_candidates, max(duration - 0.5, 0.0), "end_state", 0.55)

    # Rule 2: explicit visual events (scene shifts, errors, etc.).
    for idx, event in enumerate(visual_events):
        event_name = str(event.get("event") or "visual_event")
        ts = event.get("timestamp_seconds")
        if ts is None:
            ts = ((idx + 1) / (len(visual_events) + 1)) * duration
        _insert_frame(frame_candidates, float(ts), _frame_reason(event_name), float(event.get("confidence", 0.7) or 0.7))

    # Rule 3: video-derived process candidates.
    video_candidates = [c for c in process_candidates if str(c.get("source", "")).lower() == "video"]
    for idx, candidate in enumerate(video_candidates):
        ts = candidate.get("timestamp_seconds")
        if ts is None:
            ts = ((idx + 1) / (len(video_candidates) + 1)) * duration
        _insert_frame(frame_candidates, float(ts), "process_hotspot", 0.78)

    # Rule 4: transcript timestamps if present.
    for ts in _extract_timestamps_from_text(transcript_text):
        if ts <= duration + 1:
            _insert_frame(frame_candidates, ts, "transcript_anchor", 0.74)

    return _dedupe_and_limit(frame_candidates, max_frames=max_frames, min_gap_seconds=min_gap_seconds)
