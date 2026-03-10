import os
from pathlib import Path
import shutil
from typing import Optional

from fastapi import UploadFile

MAX_FILE_SIZE_MB = 500
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
AUDIO_MIME_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/mp4", "audio/m4a", "audio/x-m4a"}
TRANSCRIPT_MIME_TYPES = {"text/plain", "text/markdown", "application/pdf"}


class ValidationError(Exception):
    def __init__(self, code: str, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _check_mime(file: UploadFile, allowed: set[str], field_name: str) -> None:
    content_type = file.content_type or ""
    if content_type not in allowed:
        raise ValidationError(
            code="ERR_UNSUPPORTED_MIME",
            message=f"Unsupported MIME type for {field_name}: {content_type}",
            details={"field": field_name, "content_type": content_type},
        )


async def _file_size(file: UploadFile) -> int:
    stream = file.file
    current = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(current)
    return size


async def _save_file(file: UploadFile, target_path: Path) -> int:
    size = 0
    try:
        with target_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_SIZE_BYTES:
                    raise ValidationError(
                        code="ERR_FILE_TOO_LARGE",
                        message=f"File exceeds {MAX_FILE_SIZE_MB} MB limit.",
                        details={"filename": file.filename, "max_mb": MAX_FILE_SIZE_MB},
                    )
                out.write(chunk)
    finally:
        await file.close()
    return size


def _safe_filename(raw_name: Optional[str], fallback: str) -> str:
    cleaned = Path((raw_name or "").strip()).name
    return cleaned if cleaned else fallback


async def validate_and_persist_inputs(
    job_id: str,
    uploads_dir: Path,
    video_file: Optional[UploadFile],
    audio_file: Optional[UploadFile],
    transcript_file: Optional[UploadFile],
) -> dict:
    if not any([video_file, audio_file, transcript_file]):
        raise ValidationError("ERR_INVALID_INPUT", "At least one input file is required.")

    job_dir = uploads_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"video": None, "audio": None, "transcript": None}

    try:
        if video_file:
            _check_mime(video_file, VIDEO_MIME_TYPES, "video_file")
            if await _file_size(video_file) > MAX_FILE_SIZE_BYTES:
                raise ValidationError("ERR_FILE_TOO_LARGE", f"Video file exceeds {MAX_FILE_SIZE_MB} MB limit.")
            safe_name = _safe_filename(video_file.filename, "video.bin")
            path = job_dir / safe_name
            size = await _save_file(video_file, path)
            manifest["video"] = {
                "filename": safe_name,
                "content_type": video_file.content_type,
                "size_bytes": size,
                "storage_key": str(path),
            }

        if audio_file:
            _check_mime(audio_file, AUDIO_MIME_TYPES, "audio_file")
            if await _file_size(audio_file) > MAX_FILE_SIZE_BYTES:
                raise ValidationError("ERR_FILE_TOO_LARGE", f"Audio file exceeds {MAX_FILE_SIZE_MB} MB limit.")
            safe_name = _safe_filename(audio_file.filename, "audio.bin")
            path = job_dir / safe_name
            size = await _save_file(audio_file, path)
            manifest["audio"] = {
                "filename": safe_name,
                "content_type": audio_file.content_type,
                "size_bytes": size,
                "storage_key": str(path),
            }

        if transcript_file:
            _check_mime(transcript_file, TRANSCRIPT_MIME_TYPES, "transcript_file")
            if await _file_size(transcript_file) > MAX_FILE_SIZE_BYTES:
                raise ValidationError("ERR_FILE_TOO_LARGE", f"Transcript file exceeds {MAX_FILE_SIZE_MB} MB limit.")
            safe_name = _safe_filename(transcript_file.filename, "transcript.txt")
            path = job_dir / safe_name
            size = await _save_file(transcript_file, path)
            manifest["transcript"] = {
                "filename": safe_name,
                "content_type": transcript_file.content_type,
                "size_bytes": size,
                "storage_key": str(path),
            }
    except ValidationError:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    return manifest
