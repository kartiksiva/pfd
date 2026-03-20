from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional


_VTT_TIMESTAMP_RE = re.compile(
    r"^\s*\d{2,}:\d{2}(?::\d{2})?\.\d{3}\s+-->\s+\d{2,}:\d{2}(?::\d{2})?\.\d{3}(?:\s+.*)?\s*$"
)
_VTT_CUE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")
_VTT_NOTE_RE = re.compile(r"^\s*NOTE(?:\s+.*)?$", flags=re.IGNORECASE)


@dataclass
class TranscriptAsset:
    text: str
    format: Optional[str] = None


def _is_webvtt_content(raw_text: str, filename: str = "", content_type: str = "") -> bool:
    normalized_name = str(filename or "").lower()
    normalized_type = str(content_type or "").lower()
    stripped = raw_text.lstrip("\ufeff \t\r\n")
    return (
        normalized_name.endswith(".vtt")
        or normalized_type == "text/vtt"
        or stripped.startswith("WEBVTT")
    )


def _normalize_webvtt(raw_text: str) -> str:
    lines = raw_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    utterances = []
    cue_lines = []
    in_note_block = False

    def flush_cue() -> None:
        nonlocal cue_lines
        if not cue_lines:
            return
        text = " ".join(part.strip() for part in cue_lines if part.strip())
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            utterances.append(text)
        cue_lines = []

    for raw_line in lines:
        line = raw_line.strip()

        if in_note_block:
            if not line:
                in_note_block = False
            continue

        if not line:
            flush_cue()
            continue
        if line == "WEBVTT":
            continue
        if _VTT_NOTE_RE.match(line):
            flush_cue()
            in_note_block = True
            continue
        if line.startswith(("STYLE", "REGION")):
            flush_cue()
            continue
        if _VTT_CUE_NUMBER_RE.match(line):
            continue
        if _VTT_TIMESTAMP_RE.match(line):
            continue
        cue_lines.append(line)

    flush_cue()
    return "\n".join(utterances).strip()


def normalize_transcript_text(raw_text: str, filename: str = "", content_type: str = "") -> TranscriptAsset:
    stripped = (raw_text or "").strip()
    if not stripped:
        return TranscriptAsset(text="", format=None)
    if _is_webvtt_content(raw_text, filename=filename, content_type=content_type):
        return TranscriptAsset(text=_normalize_webvtt(raw_text), format="webvtt")
    return TranscriptAsset(text=stripped, format=None)


def read_transcript_asset(input_manifest: dict) -> Optional[TranscriptAsset]:
    entry = input_manifest.get("transcript")
    if not entry:
        return None
    path = entry.get("storage_key")
    if not path:
        return None
    try:
        raw_text = Path(path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return normalize_transcript_text(
        raw_text,
        filename=str(entry.get("filename") or Path(path).name),
        content_type=str(entry.get("content_type") or ""),
    )
