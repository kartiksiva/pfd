from typing import Dict

from app.config import get_settings
from app.providers.base import EvidencePayload, ProviderAdapter, has_audio_or_video, read_transcript_file
from app.providers.structured_extraction import extract_with_llm


class OpenAIAdapter(ProviderAdapter):
    provider_name = "openai"
    extraction_model = "gpt-4.1"

    def resolve_model_plan(self) -> Dict:
        return {
            "provider": "openai",
            "transcription_model": "gpt-4o-mini-transcribe",
            "multimodal_model": "gpt-4.1",
            "generation_model": "gpt-4.1",
            "fallback_transcription": {"provider": "google", "model": "gemini-2.5-flash"},
        }

    def transcribe(self, input_manifest: Dict) -> str:
        # MVP adapter scaffold:
        # - transcript input: use provided text file
        # - audio/video input: placeholder transcription result
        existing = read_transcript_file(input_manifest)
        if existing:
            return existing
        if has_audio_or_video(input_manifest):
            return "[OpenAI transcription placeholder]"
        return ""

    def build_evidence(self, input_manifest: Dict, transcript_text: str) -> EvidencePayload:
        settings = get_settings()
        structured = None
        if settings.llm_enabled:
            structured = extract_with_llm(
                provider=self.provider_name,
                transcript_text=transcript_text,
                api_key=settings.openai_api_key,
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
            candidates.append({"source": "video", "action": "detect_visual_handoffs"})
        if input_manifest.get("audio"):
            candidates.append({"source": "audio", "action": "extract_spoken_steps"})
        return EvidencePayload(
            provider=self.provider_name,
            transcript_text=transcript_text,
            visual_events=[{"event": "screen_transition", "confidence": 0.65}] if input_manifest.get("video") else [],
            process_candidates=candidates,
            confidence=float(structured.get("confidence", 0.76)) if structured else (0.72 if candidates else 0.0),
            structured_extraction=structured,
        )

    def estimate_cost(self, input_manifest: Dict) -> Dict:
        base = 0.22
        if input_manifest.get("video"):
            base += 0.28
        if input_manifest.get("audio"):
            base += 0.12
        return {
            "currency": "USD",
            "estimated_total": round(base, 2),
            "estimated_per_media_hour": 3.4,
            "input_tokens": 0,
            "output_tokens": 0,
            "audio_seconds_processed": 0,
            "video_seconds_processed": 0,
        }
