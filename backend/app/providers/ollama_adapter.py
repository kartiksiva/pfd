from typing import Dict

from app.config import get_settings
from app.pipelines.frame_extraction import extract_key_frame_images
from app.pipelines.frame_selector import select_key_frames
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

    def transcribe(self, input_manifest: Dict, use_full_media: bool = False) -> str:
        existing = read_transcript_file(input_manifest)
        if existing:
            return existing
        if has_audio_or_video(input_manifest) and use_full_media:
            return "[Ollama transcription placeholder]"
        return ""

    def build_evidence(
        self,
        input_manifest: Dict,
        transcript_text: str,
        processing_profile: str = "balanced",
        use_full_media: bool = False,
    ) -> EvidencePayload:
        settings = get_settings()
        candidates = []
        if input_manifest.get("video"):
            candidates.append({"source": "video", "action": "local_frame_inference"})
        if input_manifest.get("audio"):
            candidates.append({"source": "audio", "action": "local_audio_inference"})
        if transcript_text:
            candidates.append({"source": "transcript", "action": "extract_steps", "summary": transcript_text[:180]})

        visual_events = [{"event": "local_model_inference", "confidence": 0.6}] if input_manifest.get("video") else []
        key_frames = select_key_frames(
            input_manifest=input_manifest,
            evidence={
                "transcript_text": transcript_text,
                "visual_events": visual_events,
                "process_candidates": candidates,
            },
        )
        frame_images = extract_key_frame_images(
            video_path=str((input_manifest.get("video") or {}).get("storage_key") or ""),
            key_frames=key_frames,
            max_images=12,
        )
        if input_manifest.get("video") and not frame_images:
            candidates.append(
                {
                    "source": "video",
                    "action": "frame_extraction_unavailable",
                    "summary": "No key frames extracted. Install ffmpeg or upload transcript text from recording.",
                }
            )

        structured = None
        if settings.llm_enabled and (transcript_text or frame_images):
            structured = extract_with_llm(
                provider=self.provider_name,
                transcript_text=transcript_text,
                api_key=None,
                model=settings.ollama_model,
                ollama_base_url=settings.ollama_base_url,
                frame_images=frame_images,
            )
        if structured and structured.get("process_steps"):
            candidates = [
                {"source": "llm", "action": "extract_steps", "summary": step.get("summary", "")}
                for step in structured.get("process_steps", [])[:30]
            ] + [c for c in candidates if c.get("source") != "transcript"]
        return EvidencePayload(
            provider=self.provider_name,
            transcript_text=transcript_text,
            visual_events=visual_events,
            process_candidates=candidates,
            confidence=float(structured.get("confidence", 0.7)) if structured else (0.62 if candidates else 0.0),
            structured_extraction=structured,
        )

    def estimate_cost(self, input_manifest: Dict, use_full_media: bool = False) -> Dict:
        return {
            "currency": "USD",
            "estimated_total": 0.0,
            "estimated_per_media_hour": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "audio_seconds_processed": 0,
            "video_seconds_processed": 0,
        }
