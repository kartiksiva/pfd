from typing import Dict

from app.config import get_settings
from app.providers.base import EvidencePayload, ProviderAdapter, has_audio_or_video, read_transcript_file
from app.providers.structured_extraction import extract_with_llm


class OllamaAdapter(ProviderAdapter):
    provider_name = "ollama"

    def resolve_model_plan(self) -> Dict:
        settings = get_settings()
        return {
            "provider": "ollama",
            "transcription_model": settings.ollama_model,
            "multimodal_model": settings.ollama_model,
            "generation_model": settings.ollama_model,
            "fallback_transcription": {"provider": "google", "model": "gemini-2.5-flash"},
        }

    def transcribe(self, input_manifest: Dict) -> str:
        existing = read_transcript_file(input_manifest)
        if existing:
            return existing
        if has_audio_or_video(input_manifest):
            return "[Ollama transcription placeholder]"
        return ""

    def build_evidence(self, input_manifest: Dict, transcript_text: str) -> EvidencePayload:
        settings = get_settings()
        structured = None
        if settings.llm_enabled:
            structured = extract_with_llm(
                provider=self.provider_name,
                transcript_text=transcript_text,
                api_key=None,
                model=settings.ollama_model,
                ollama_base_url=settings.ollama_base_url,
            )
        candidates = []
        if structured and structured.get("process_steps"):
            candidates = [
                {"source": "llm", "action": "extract_steps", "summary": step.get("summary", "")}
                for step in structured.get("process_steps", [])[:30]
            ]
        elif transcript_text:
            candidates.append({"source": "transcript", "action": "extract_steps", "summary": transcript_text[:180]})
        if input_manifest.get("video"):
            candidates.append({"source": "video", "action": "local_frame_inference"})
        if input_manifest.get("audio"):
            candidates.append({"source": "audio", "action": "local_audio_inference"})
        return EvidencePayload(
            provider=self.provider_name,
            transcript_text=transcript_text,
            visual_events=[{"event": "local_model_inference", "confidence": 0.6}] if input_manifest.get("video") else [],
            process_candidates=candidates,
            confidence=float(structured.get("confidence", 0.7)) if structured else (0.65 if candidates else 0.0),
            structured_extraction=structured,
        )

    def estimate_cost(self, input_manifest: Dict) -> Dict:
        return {
            "currency": "USD",
            "estimated_total": 0.0,
            "estimated_per_media_hour": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "audio_seconds_processed": 0,
            "video_seconds_processed": 0,
        }
