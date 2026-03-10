from typing import Dict

from app.config import get_settings
from app.providers.base import EvidencePayload, ProviderAdapter, has_audio_or_video, read_transcript_file
from app.providers.media_transcription import transcribe_with_google
from app.providers.structured_extraction import extract_with_llm


class GoogleAdapter(ProviderAdapter):
    provider_name = "google"
    extraction_model = "gemini-2.5-pro"

    def resolve_model_plan(self) -> Dict:
        return {
            "provider": "google",
            "transcription_model": "gemini-2.5-flash",
            "multimodal_model": "gemini-2.5-pro",
            "generation_model": "gemini-2.5-pro",
            "fallback_transcription": {"provider": "openai", "model": "gpt-4o-mini-transcribe"},
        }

    def transcribe(self, input_manifest: Dict) -> str:
        existing = read_transcript_file(input_manifest)
        if existing:
            return existing
        if has_audio_or_video(input_manifest):
            settings = get_settings()
            return transcribe_with_google(
                input_manifest=input_manifest,
                api_key=settings.google_api_key,
                model=self.resolve_model_plan()["transcription_model"],
            )
        return ""

    def build_evidence(self, input_manifest: Dict, transcript_text: str) -> EvidencePayload:
        settings = get_settings()
        structured = None
        if settings.llm_enabled:
            structured = extract_with_llm(
                provider=self.provider_name,
                transcript_text=transcript_text,
                api_key=settings.google_api_key,
                model=self.extraction_model,
            )
        candidates = []
        if structured and structured.get("process_steps"):
            candidates = [
                {
                    "source": "llm",
                    "action": "extract_steps",
                    "summary": step.get("summary", ""),
                }
                for step in structured.get("process_steps", [])[:30]
            ]
        elif transcript_text:
            candidates.append({"source": "transcript", "action": "extract_steps", "summary": transcript_text[:180]})
        if input_manifest.get("video"):
            candidates.append({"source": "video", "action": "segment_process_frames"})
        if input_manifest.get("audio"):
            candidates.append({"source": "audio", "action": "infer_activity_timeline"})
        return EvidencePayload(
            provider=self.provider_name,
            transcript_text=transcript_text,
            visual_events=[{"event": "ui_context_shift", "confidence": 0.68}] if input_manifest.get("video") else [],
            process_candidates=candidates,
            confidence=float(structured.get("confidence", 0.78)) if structured else (0.74 if candidates else 0.0),
            structured_extraction=structured,
        )

    def estimate_cost(self, input_manifest: Dict) -> Dict:
        base = 0.20
        if input_manifest.get("video"):
            base += 0.24
        if input_manifest.get("audio"):
            base += 0.10
        return {
            "currency": "USD",
            "estimated_total": round(base, 2),
            "estimated_per_media_hour": 3.1,
            "input_tokens": 0,
            "output_tokens": 0,
            "audio_seconds_processed": 0,
            "video_seconds_processed": 0,
        }
