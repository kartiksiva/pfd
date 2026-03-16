from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import get_settings

AZURE_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
_TRANSCRIPTION_PROMPT_OAI = (
    "Transcribe this media to plain English text for business process analysis. "
    "Keep wording faithful and concise. "
    "Remove speaker labels (e.g. 'Speaker 1:', 'Interviewer:') and timestamps. "
    "Lightly clean obvious disfluencies such as 'um' and 'uh' only when meaning is "
    "entirely unchanged; preserve hesitations or self-corrections that signal uncertainty "
    "in the described process. "
    "Do not add section headings, bullet points, or markdown."
)
_TRANSCRIPTION_PROMPT_GOOGLE = (
    "Transcribe this media in English for business process documentation. "
    "Return plain text only - no JSON, no markdown, no commentary. "
    "Remove speaker labels and timestamps. "
    "Lightly clean obvious disfluencies such as 'um' and 'uh' only when meaning is "
    "entirely unchanged; preserve hesitations or self-corrections that signal uncertainty "
    "in the described process. "
    "Preserve all named entities, system names, numbers, and SLA commitments exactly as spoken. "
    "Separate speaker turns with a blank line."
)


def _normalize_azure_mode(mode: Optional[str]) -> str:
    normalized = str(mode or "auto").strip().lower()
    return normalized if normalized in {"openai_v1", "deployment", "auto"} else "auto"


def _azure_mode_candidates(mode: Optional[str]) -> list[str]:
    normalized = _normalize_azure_mode(mode)
    if normalized == "openai_v1":
        return ["openai_v1"]
    if normalized == "deployment":
        return ["deployment"]
    return ["openai_v1", "deployment"]


def _trim_error_body(text: str, limit: int = 180) -> str:
    compact = " ".join(str(text or "").split())
    return compact[:limit]


def _collect_media_entries(input_manifest: Dict) -> List[Tuple[str, Dict]]:
    entries: List[Tuple[str, Dict]] = []
    for source in ("audio", "video"):
        entry = input_manifest.get(source) or {}
        if entry.get("storage_key"):
            entries.append((source, entry))
    return entries


def _read_text_from_candidate(payload: Dict) -> str:
    parts = (
        payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [])
    )
    text_parts = [str(part.get("text", "")).strip() for part in parts if part.get("text")]
    return "\n".join([part for part in text_parts if part]).strip()


def transcribe_with_openai(input_manifest: Dict, api_key: Optional[str], model: str) -> str:
    if not api_key:
        return ""

    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {api_key}"}
    prompt = _TRANSCRIPTION_PROMPT_OAI

    transcripts: List[str] = []
    errors: List[str] = []
    with httpx.Client(timeout=180.0) as client:
        for source, entry in _collect_media_entries(input_manifest):
            file_path = Path(str(entry.get("storage_key", "")))
            if not file_path.exists():
                errors.append(f"{source}: file_not_found")
                continue
            mime_type = entry.get("content_type", "application/octet-stream")
            with file_path.open("rb") as f:
                files = {"file": (entry.get("filename") or file_path.name, f, mime_type)}
                data = {"model": model, "response_format": "json", "language": "en", "prompt": prompt}
                try:
                    response = client.post(url, headers=headers, data=data, files=files)
                    response.raise_for_status()
                    payload = response.json()
                    text = str(payload.get("text", "")).strip()
                    if text:
                        transcripts.append(f"[{source}] {text}")
                except Exception as exc:
                    errors.append(f"{source}: {exc}")

    if transcripts:
        return "\n\n".join(transcripts).strip()
    if errors:
        raise RuntimeError(f"openai_transcription_failed: {'; '.join(errors[:3])}")
    return ""


def transcribe_with_azure_openai(
    input_manifest: Dict,
    api_key: Optional[str],
    endpoint: Optional[str],
    deployment: str,
    api_version: str = "2024-10-21",
    mode: str = "auto",
) -> str:
    media_entries = _collect_media_entries(input_manifest)
    if not media_entries:
        return ""
    if not api_key or not endpoint or not deployment:
        raise RuntimeError("azure_openai_config_invalid: missing endpoint, api_key, or deployment")

    base = endpoint.rstrip("/")
    prompt = _TRANSCRIPTION_PROMPT_OAI

    transcripts: List[str] = []
    errors: List[str] = []
    with httpx.Client(timeout=180.0) as client:
        for source, entry in media_entries:
            file_path = Path(str(entry.get("storage_key", "")))
            if not file_path.exists():
                errors.append(f"{source}: file_not_found")
                continue
            size_bytes = file_path.stat().st_size
            if size_bytes > AZURE_MAX_FILE_SIZE_BYTES:
                errors.append(
                    f"{source}: provider_file_too_large:{size_bytes}_bytes_exceeds_azure_25mb_limit"
                )
                continue
            mime_type = entry.get("content_type", "application/octet-stream")
            with file_path.open("rb") as f:
                files = {"file": (entry.get("filename") or file_path.name, f, mime_type)}
                attempt_errors: List[str] = []
                text = ""
                for selected_mode in _azure_mode_candidates(mode):
                    if selected_mode == "openai_v1":
                        url = f"{base}/openai/v1/audio/transcriptions"
                        headers = {"Authorization": f"Bearer {api_key}"}
                        data = {
                            "model": deployment,
                            "response_format": "json",
                            "language": "en",
                            "prompt": prompt,
                        }
                    else:
                        url = (
                            f"{base}/openai/deployments/{deployment}/audio/transcriptions"
                            f"?api-version={api_version}"
                        )
                        headers = {"api-key": api_key}
                        data = {"response_format": "json", "language": "en", "prompt": prompt}
                    try:
                        f.seek(0)
                        response = client.post(url, headers=headers, data=data, files=files)
                        if response.status_code >= 400:
                            raise RuntimeError(
                                f"http_{response.status_code}:{_trim_error_body(response.text)}"
                            )
                        payload = response.json() if "json" in response.headers.get("content-type", "").lower() else {}
                        text = str(payload.get("text", "")).strip()
                        if not text:
                            text = str(getattr(response, "text", "")).strip()
                        if text:
                            break
                        raise RuntimeError("empty_transcription_text")
                    except Exception as exc:
                        attempt_errors.append(f"{selected_mode}:{exc}")
                if text:
                    transcripts.append(f"[{source}] {text}")
                else:
                    errors.append(f"{source}: {' | '.join(attempt_errors[:2])}")

    if transcripts:
        return "\n\n".join(transcripts).strip()
    if errors:
        raise RuntimeError(f"azure_openai_transcription_failed: {'; '.join(errors[:3])}")
    return ""


def _google_upload_file(client: httpx.Client, api_key: str, file_path: Path, filename: str, mime_type: str) -> Dict:
    start_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
    metadata = {"file": {"display_name": filename}}
    start_headers = {
        "X-Goog-Upload-Protocol": "resumable",
        "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(file_path.stat().st_size),
        "X-Goog-Upload-Header-Content-Type": mime_type,
        "Content-Type": "application/json",
    }
    start_response = client.post(start_url, headers=start_headers, content=json.dumps(metadata))
    start_response.raise_for_status()
    upload_url = start_response.headers.get("x-goog-upload-url")
    if not upload_url:
        raise RuntimeError("missing_google_upload_url")

    upload_headers = {
        "X-Goog-Upload-Command": "upload, finalize",
        "X-Goog-Upload-Offset": "0",
        "Content-Type": mime_type,
    }
    with file_path.open("rb") as f:
        upload_response = client.post(upload_url, headers=upload_headers, content=f)
    upload_response.raise_for_status()
    payload = upload_response.json()
    return payload.get("file", payload)


def _google_wait_until_active(client: httpx.Client, api_key: str, file_name: str, timeout_seconds: float = 120.0) -> Dict:
    file_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
    start = time.monotonic()
    last_payload: Dict = {}
    while (time.monotonic() - start) < timeout_seconds:
        response = client.get(file_url)
        response.raise_for_status()
        payload = response.json().get("file", response.json())
        last_payload = payload
        state = str(payload.get("state", "")).upper()
        if state in {"ACTIVE", "READY"}:
            return payload
        if state in {"FAILED", "ERROR"}:
            raise RuntimeError(f"google_file_processing_failed:{state}")
        time.sleep(1.0)
    raise RuntimeError(f"google_file_processing_timeout:{last_payload.get('state', 'UNKNOWN')}")


def _google_delete_file(client: httpx.Client, api_key: str, file_name: str) -> None:
    if not file_name:
        return
    delete_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
    try:
        client.delete(delete_url)
    except Exception:
        return


def transcribe_with_google(input_manifest: Dict, api_key: Optional[str], model: str) -> str:
    if not api_key:
        return ""

    prompt = _TRANSCRIPTION_PROMPT_GOOGLE
    transcripts: List[str] = []
    errors: List[str] = []

    with httpx.Client(timeout=240.0) as client:
        for source, entry in _collect_media_entries(input_manifest):
            file_path = Path(str(entry.get("storage_key", "")))
            if not file_path.exists():
                errors.append(f"{source}: file_not_found")
                continue

            mime_type = str(entry.get("content_type") or "application/octet-stream")
            filename = str(entry.get("filename") or file_path.name)
            uploaded_name = ""
            try:
                file_obj = _google_upload_file(
                    client=client,
                    api_key=api_key,
                    file_path=file_path,
                    filename=filename,
                    mime_type=mime_type,
                )
                uploaded_name = str(file_obj.get("name", ""))
                file_obj = _google_wait_until_active(client=client, api_key=api_key, file_name=uploaded_name)
                file_uri = str(file_obj.get("uri", ""))
                if not file_uri:
                    raise RuntimeError("google_file_uri_missing")

                gen_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                body = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": prompt},
                                {"file_data": {"mime_type": mime_type, "file_uri": file_uri}},
                            ],
                        }
                    ],
                    "generationConfig": {"temperature": 0.0},
                }
                response = client.post(gen_url, json=body)
                response.raise_for_status()
                text = _read_text_from_candidate(response.json())
                if text:
                    transcripts.append(f"[{source}] {text}")
            except Exception as exc:
                errors.append(f"{source}: {exc}")
            finally:
                if uploaded_name:
                    _google_delete_file(client=client, api_key=api_key, file_name=uploaded_name)

    if transcripts:
        return "\n\n".join(transcripts).strip()
    if errors:
        raise RuntimeError(f"google_transcription_failed: {'; '.join(errors[:3])}")
    return ""
