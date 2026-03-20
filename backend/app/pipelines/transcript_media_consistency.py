from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional

from app.config import get_settings
from app.providers.media_transcription import (
    transcribe_with_azure_openai,
    transcribe_with_google,
    transcribe_with_openai,
)
from app.transcript_utils import normalize_transcript_text


_SPEAKER_LABEL_RE = re.compile(
    r"^(?:\*{0,2})?(?:[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.&()/:-]+){0,5})(?:\s*\([^)]+\))?\s*:\s*"
)


def _strip_speaker_labels(text: str) -> str:
    cleaned_lines: List[str] = []
    for line in str(text or "").splitlines():
        updated = str(line).strip()
        for _ in range(3):
            candidate = _SPEAKER_LABEL_RE.sub("", updated, count=1).strip()
            if candidate == updated:
                break
            updated = candidate
        if updated:
            cleaned_lines.append(updated)
    return "\n".join(cleaned_lines)


def _normalize_for_comparison(text: str) -> str:
    asset = normalize_transcript_text(str(text or ""), filename="transcript.vtt")
    cleaned = _strip_speaker_labels(asset.text or str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _truncate_for_comparison(text: str, max_chars: int = 2000) -> str:
    cleaned = _normalize_for_comparison(text)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rsplit(" ", 1)[0].strip()


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _similarity_score(left: str, right: str) -> float:
    left_norm = _truncate_for_comparison(left)
    right_norm = _truncate_for_comparison(right, max_chars=max(len(left_norm), 1))
    if not left_norm or not right_norm:
        return 0.0
    left_tokens = set(_tokenize(left_norm))
    right_tokens = set(_tokenize(right_norm))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    seq = SequenceMatcher(a=left_norm, b=right_norm).ratio()
    return round((overlap * 0.4) + (seq * 0.6), 3)


def should_check_transcript_media_consistency(input_manifest: Dict, transcript_text: str) -> bool:
    settings = get_settings()
    if not settings.transcript_media_check_enabled:
        return False
    has_media = bool((input_manifest.get("audio") or {}).get("storage_key") or (input_manifest.get("video") or {}).get("storage_key"))
    has_transcript_file = bool((input_manifest.get("transcript") or {}).get("storage_key"))
    if not has_media or not has_transcript_file:
        return False
    normalized = _truncate_for_comparison(transcript_text, max_chars=10000)
    return len(normalized) >= settings.transcript_media_min_transcript_chars


def _verification_result(
    *,
    checked: bool,
    provider: str,
    verdict: str,
    reasons: List[str],
    sample_source: str = "",
    similarity_score: Optional[float] = None,
    transcript_chars: int = 0,
    verification_chars: int = 0,
) -> Dict:
    settings = get_settings()
    return {
        "checked": checked,
        "provider": provider,
        "sample_source": sample_source,
        "sample_window_seconds": settings.transcript_media_sample_seconds,
        "uploaded_transcript_chars_compared": transcript_chars,
        "verification_transcript_chars_compared": verification_chars,
        "similarity_score": similarity_score,
        "verdict": verdict,
        "reasons": reasons,
    }


def _verification_transcript(provider: str, input_manifest: Dict) -> str:
    settings = get_settings()
    if provider == "azure_openai":
        return transcribe_with_azure_openai(
            input_manifest=input_manifest,
            api_key=settings.azure_openai_api_key,
            endpoint=settings.azure_openai_endpoint,
            deployment=settings.azure_openai_transcription_deployment or "",
            api_version=settings.azure_openai_api_version,
            mode=settings.azure_openai_mode,
        )
    if provider == "openai":
        return transcribe_with_openai(
            input_manifest=input_manifest,
            api_key=settings.openai_api_key,
            model="gpt-4o-mini-transcribe",
        )
    if provider == "google":
        return transcribe_with_google(
            input_manifest=input_manifest,
            api_key=settings.google_api_key,
            model="gemini-2.5-flash",
        )
    raise RuntimeError("provider_verification_unavailable")


def verify_transcript_media_consistency(
    provider: str,
    input_manifest: Dict,
    transcript_text: str,
) -> Dict:
    normalized_transcript = _truncate_for_comparison(transcript_text)
    if not should_check_transcript_media_consistency(input_manifest, transcript_text):
        return _verification_result(
            checked=False,
            provider=provider,
            verdict="not_checked",
            reasons=["eligibility_conditions_not_met"],
            transcript_chars=len(normalized_transcript),
        )
    if provider == "ollama":
        return _verification_result(
            checked=False,
            provider=provider,
            verdict="unsupported",
            reasons=["provider_verification_unavailable"],
            transcript_chars=len(normalized_transcript),
        )
    try:
        verification_text = _verification_transcript(provider, input_manifest)
    except Exception as exc:
        return _verification_result(
            checked=True,
            provider=provider,
            verdict="inconclusive",
            reasons=[f"verification_transcription_failed:{type(exc).__name__}"],
            sample_source="verification_transcription_failed",
            transcript_chars=len(normalized_transcript),
        )

    verification_sample = _truncate_for_comparison(verification_text, max_chars=max(len(normalized_transcript), 1))
    transcript_sample = _truncate_for_comparison(transcript_text, max_chars=max(len(verification_sample), 1))
    score = _similarity_score(transcript_sample, verification_sample)
    settings = get_settings()
    if score >= settings.transcript_media_match_threshold:
        verdict = "match"
        reasons = ["media_transcript_similarity_above_match_threshold"]
    elif score <= settings.transcript_media_mismatch_threshold:
        verdict = "suspected_mismatch"
        reasons = ["media_transcript_similarity_below_mismatch_threshold"]
    else:
        verdict = "inconclusive"
        reasons = ["media_transcript_similarity_between_thresholds"]
    return _verification_result(
        checked=True,
        provider=provider,
        verdict=verdict,
        reasons=reasons,
        sample_source="full_media_transcription_truncated_for_comparison",
        similarity_score=score,
        transcript_chars=len(transcript_sample),
        verification_chars=len(verification_sample),
    )
