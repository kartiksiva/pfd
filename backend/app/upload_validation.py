import mimetypes
import os
from pathlib import Path
import shutil
from typing import Optional

from fastapi import UploadFile

MAX_FILE_SIZE_MB = 500
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-msvideo"}
AUDIO_MIME_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/mp4a-latm",
}
TRANSCRIPT_MIME_TYPES = {"text/plain", "text/markdown", "application/pdf"}
TRANSCRIPT_MIME_TYPES.add("text/vtt")


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


def _persist_local_file(source_path: Path, target_path: Path, max_size_error: str) -> int:
    size = source_path.stat().st_size
    if size > MAX_FILE_SIZE_BYTES:
        raise ValidationError("ERR_FILE_TOO_LARGE", max_size_error)
    shutil.copy2(source_path, target_path)
    return size


def _manifest_entry(path: Path, content_type: str, size: int) -> dict:
    return {
        "filename": path.name,
        "content_type": content_type,
        "size_bytes": size,
        "storage_key": str(path),
    }


def _guess_demo_content_type(path: Path, fallback: str) -> str:
    suffix_map = {
        ".mov": "video/quicktime",
        ".mp4": "video/mp4",
        ".avi": "video/x-msvideo",
        ".m4a": "audio/mp4",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
    }
    guessed = mimetypes.guess_type(path.name)[0]
    return guessed or suffix_map.get(path.suffix.lower(), fallback)


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
    inputs_dir = job_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"video": None, "audio": None, "transcript": None}

    try:
        if video_file:
            _check_mime(video_file, VIDEO_MIME_TYPES, "video_file")
            if await _file_size(video_file) > MAX_FILE_SIZE_BYTES:
                raise ValidationError("ERR_FILE_TOO_LARGE", f"Video file exceeds {MAX_FILE_SIZE_MB} MB limit.")
            safe_name = _safe_filename(video_file.filename, "video.bin")
            path = inputs_dir / safe_name
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
            path = inputs_dir / safe_name
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
            path = inputs_dir / safe_name
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


def persist_demo_inputs(
    job_id: str,
    uploads_dir: Path,
    demo_dir: Path,
    video_name: str = "DemoVideo.mov",
    audio_name: str = "DemoAudio.m4a",
) -> dict:
    video_source = demo_dir / video_name
    audio_source = demo_dir / audio_name
    if not video_source.exists() and not audio_source.exists():
        raise ValidationError(
            "ERR_INVALID_INPUT",
            "Demo inputs are not available on the server.",
            details={"demo_dir": str(demo_dir)},
        )

    job_dir = uploads_dir / job_id
    inputs_dir = job_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"video": None, "audio": None, "transcript": None}

    try:
        if video_source.exists():
            video_mime = _guess_demo_content_type(video_source, "video/quicktime")
            if video_mime not in VIDEO_MIME_TYPES:
                raise ValidationError(
                    "ERR_UNSUPPORTED_MIME",
                    f"Unsupported MIME type for demo video: {video_mime}",
                    details={"field": "video_file", "content_type": video_mime},
                )
            video_target = inputs_dir / _safe_filename(video_source.name, "demo-video.bin")
            size = _persist_local_file(
                video_source,
                video_target,
                f"Demo video exceeds {MAX_FILE_SIZE_MB} MB limit.",
            )
            manifest["video"] = _manifest_entry(video_target, video_mime, size)

        if audio_source.exists():
            audio_mime = _guess_demo_content_type(audio_source, "audio/mp4")
            if audio_mime not in AUDIO_MIME_TYPES:
                raise ValidationError(
                    "ERR_UNSUPPORTED_MIME",
                    f"Unsupported MIME type for demo audio: {audio_mime}",
                    details={"field": "audio_file", "content_type": audio_mime},
                )
            audio_target = inputs_dir / _safe_filename(audio_source.name, "demo-audio.bin")
            size = _persist_local_file(
                audio_source,
                audio_target,
                f"Demo audio exceeds {MAX_FILE_SIZE_MB} MB limit.",
            )
            manifest["audio"] = _manifest_entry(audio_target, audio_mime, size)
    except ValidationError:
        shutil.rmtree(job_dir, ignore_errors=True)
        raise

    if not any([manifest["video"], manifest["audio"]]):
        shutil.rmtree(job_dir, ignore_errors=True)
        raise ValidationError("ERR_INVALID_INPUT", "At least one demo input file is required.")

    return manifest
