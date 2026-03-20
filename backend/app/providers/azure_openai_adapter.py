from typing import Dict

from app.config import get_settings
from app.pipelines.frame_extraction import extract_key_frame_images
from app.pipelines.frame_selector import select_key_frames
from app.providers.base import EvidencePayload, ProviderAdapter, has_audio_or_video
from app.providers.media_transcription import transcribe_with_azure_openai
from app.providers.structured_extraction import extract_with_llm_detailed
from app.transcript_utils import read_transcript_asset


class AzureOpenAIAdapter(ProviderAdapter):
    provider_name = "azure_openai"

    def resolve_model_plan(self) -> Dict:
        settings = get_settings()
        return {
            "provider": "azure_openai",
            "transcription_model": settings.azure_openai_transcription_deployment or "",
            "multimodal_model": settings.azure_openai_chat_deployment or "",
            "generation_model": settings.azure_openai_chat_deployment or "",
            "azure_api_mode": settings.azure_openai_mode,
            "azure_api_version": settings.azure_openai_api_version,
            "fallback_transcription": {"provider": "google", "model": "gemini-2.5-flash"},
        }

    @staticmethod
    def _validate_transcription_config() -> None:
        settings = get_settings()
        missing = []
        if not settings.azure_openai_api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not settings.azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not settings.azure_openai_transcription_deployment:
            missing.append("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT")
        if missing:
            raise RuntimeError(
                f"azure_openai_config_invalid: stage=transcription missing={','.join(missing)}"
            )

    @staticmethod
    def _validate_generation_config() -> None:
        settings = get_settings()
        missing = []
        if not settings.azure_openai_api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not settings.azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not settings.azure_openai_chat_deployment:
            missing.append("AZURE_OPENAI_CHAT_DEPLOYMENT")
        if missing:
            raise RuntimeError(
                f"azure_openai_config_invalid: stage=structured_extraction missing={','.join(missing)}"
            )

    def transcribe(self, input_manifest: Dict, use_full_media: bool = False) -> str:
        transcript_asset = read_transcript_asset(input_manifest)
        if transcript_asset and transcript_asset.text:
            return transcript_asset.text
        # Azure OpenAI supports full media transcription.
        # We trigger it if requested or if we are in 'balanced' mode but no manual transcript exists.
        if has_audio_or_video(input_manifest) and (use_full_media or not transcript_asset):
            settings = get_settings()
            self._validate_transcription_config()
            try:
                return transcribe_with_azure_openai(
                    input_manifest=input_manifest,
                    api_key=settings.azure_openai_api_key,
                    endpoint=settings.azure_openai_endpoint,
                    deployment=self.resolve_model_plan()["transcription_model"],
                    api_version=settings.azure_openai_api_version,
                    mode=settings.azure_openai_mode,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"azure_openai stage=transcription mode={settings.azure_openai_mode}: {exc}"
                ) from exc
        return ""

    def build_evidence(
        self,
        input_manifest: Dict,
        transcript_text: str,
        document_template: str = "pdd",
        context_notes: str = None,
        processing_profile: str = "balanced",
        use_full_media: bool = False,
    ) -> EvidencePayload:
        settings = get_settings()
        transcript_asset = read_transcript_asset(input_manifest)
        candidates = []
        if input_manifest.get("video"):
            candidates.append({"source": "video", "action": "detect_visual_handoffs"})
        if input_manifest.get("audio"):
            candidates.append({"source": "audio", "action": "extract_spoken_steps"})
        if transcript_text:
            candidates.append({"source": "transcript", "action": "extract_steps", "summary": transcript_text[:180]})

        visual_events = [{"event": "screen_transition", "confidence": 0.65}] if input_manifest.get("video") else []
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

        structured = None
        structured_error = None
        structured_raw_preview = None
        if settings.llm_enabled and (transcript_text or frame_images):
            self._validate_generation_config()
            try:
                structured, structured_error = extract_with_llm_detailed(
                    provider=self.provider_name,
                    transcript_text=transcript_text,
                    document_template=document_template,
                    context_notes=context_notes,
                    api_key=settings.azure_openai_api_key,
                    model=self.resolve_model_plan()["generation_model"],
                    azure_endpoint=settings.azure_openai_endpoint,
                    frame_images=frame_images,
                )
                if structured_error and "Raw preview: " in structured_error:
                    structured_raw_preview = structured_error.split("Raw preview: ", 1)[1].strip() or None
            except Exception as exc:
                raise RuntimeError(
                    "azure_openai stage=structured_extraction mode="
                    f"{settings.azure_openai_mode}: {exc}"
                ) from exc
        if structured and structured.get("process_steps"):
            candidates = [
                {"source": "llm", "action": "extract_steps", "summary": step.get("summary", "")}
                for step in structured.get("process_steps", [])[:30]
            ] + [c for c in candidates if c.get("source") != "transcript"]
        return EvidencePayload(
            provider=self.provider_name,
            transcript_text=transcript_text,
            transcript_format=transcript_asset.format if transcript_asset else None,
            visual_events=visual_events,
            process_candidates=candidates,
            confidence=float(structured.get("confidence", 0.76)) if structured else (0.70 if candidates else 0.0),
            frame_images=frame_images,
            structured_extraction=structured,
            structured_extraction_error=structured_error,
            structured_extraction_raw_preview=structured_raw_preview,
        )

    def estimate_cost(self, input_manifest: Dict, use_full_media: bool = False) -> Dict:
        base = 0.22
        if input_manifest.get("video"):
            base += 0.28 if use_full_media else 0.10
        if input_manifest.get("audio"):
            base += 0.12 if use_full_media else 0.05
        return {
            "currency": "USD",
            "estimated_total": round(base, 2),
            "estimated_per_media_hour": 3.4 if use_full_media else 1.5,
            "input_tokens": 0,
            "output_tokens": 0,
            "audio_seconds_processed": 0,
            "video_seconds_processed": 0,
        }
