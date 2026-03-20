from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.transcript_utils import read_transcript_asset


@dataclass
class EvidencePayload:
    provider: str
    transcript_text: str
    visual_events: List[Dict]
    process_candidates: List[Dict]
    confidence: float
    transcript_format: Optional[str] = None
    frame_images: List[Dict] = field(default_factory=list)
    structured_extraction: Optional[Dict] = None
    structured_extraction_error: Optional[str] = None
    structured_extraction_raw_preview: Optional[str] = None


@dataclass
class AdapterResult:
    model_plan: Dict
    usage_cost_estimate: Dict
    evidence: EvidencePayload


class ProviderAdapter:
    provider_name: str = ""

    def resolve_model_plan(self) -> Dict:
        raise NotImplementedError

    def transcribe(self, input_manifest: Dict, use_full_media: bool = False) -> str:
        raise NotImplementedError

    def build_evidence(
        self,
        input_manifest: Dict,
        transcript_text: str,
        document_template: str = "pdd",
        context_notes: Optional[str] = None,
        processing_profile: str = "balanced",
        use_full_media: bool = False,
    ) -> EvidencePayload:
        raise NotImplementedError

    def estimate_cost(self, input_manifest: Dict, use_full_media: bool = False) -> Dict:
        raise NotImplementedError

    def should_use_full_media(self, processing_profile: str) -> bool:
        return processing_profile == "quality"

    def run(
        self,
        input_manifest: Dict,
        processing_profile: str = "balanced",
        document_template: str = "pdd",
        context_notes: Optional[str] = None,
    ) -> AdapterResult:
        use_full_media = self.should_use_full_media(processing_profile)
        transcript_text = self.transcribe(input_manifest, use_full_media=use_full_media)
        evidence = self.build_evidence(
            input_manifest=input_manifest,
            transcript_text=transcript_text,
            document_template=document_template,
            context_notes=context_notes,
            processing_profile=processing_profile,
            use_full_media=use_full_media,
        )
        model_plan = dict(self.resolve_model_plan() or {})
        model_plan["media_processing"] = {
            "mode": "full_media" if use_full_media else "frame_only",
            "note": (
                "Full media transcription is enabled. This mode can incur higher provider cost."
                if use_full_media
                else "Frame-only analysis is active. Upload transcript from recording for best quality and lower cost."
            ),
            "prefer_transcript_upload": True,
        }
        return AdapterResult(
            model_plan=model_plan,
            usage_cost_estimate=self.estimate_cost(input_manifest, use_full_media=use_full_media),
            evidence=evidence,
        )


def has_audio_or_video(input_manifest: Dict) -> bool:
    return bool(input_manifest.get("audio") or input_manifest.get("video"))


def transcript_file_exists(input_manifest: Dict) -> bool:
    entry = input_manifest.get("transcript")
    return bool(entry and entry.get("storage_key"))


def read_transcript_file(input_manifest: Dict) -> Optional[str]:
    asset = read_transcript_asset(input_manifest)
    return asset.text if asset else None
