from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class EvidencePayload:
    provider: str
    transcript_text: str
    visual_events: List[Dict]
    process_candidates: List[Dict]
    confidence: float
    structured_extraction: Optional[Dict] = None


@dataclass
class AdapterResult:
    model_plan: Dict
    usage_cost_estimate: Dict
    evidence: EvidencePayload


class ProviderAdapter:
    provider_name: str = ""

    def resolve_model_plan(self) -> Dict:
        raise NotImplementedError

    def transcribe(self, input_manifest: Dict) -> str:
        raise NotImplementedError

    def build_evidence(self, input_manifest: Dict, transcript_text: str) -> EvidencePayload:
        raise NotImplementedError

    def estimate_cost(self, input_manifest: Dict) -> Dict:
        raise NotImplementedError

    def run(self, input_manifest: Dict) -> AdapterResult:
        transcript_text = self.transcribe(input_manifest)
        evidence = self.build_evidence(input_manifest=input_manifest, transcript_text=transcript_text)
        return AdapterResult(
            model_plan=self.resolve_model_plan(),
            usage_cost_estimate=self.estimate_cost(input_manifest),
            evidence=evidence,
        )


def has_audio_or_video(input_manifest: Dict) -> bool:
    return bool(input_manifest.get("audio") or input_manifest.get("video"))


def transcript_file_exists(input_manifest: Dict) -> bool:
    entry = input_manifest.get("transcript")
    return bool(entry and entry.get("storage_key"))


def read_transcript_file(input_manifest: Dict) -> Optional[str]:
    entry = input_manifest.get("transcript")
    if not entry:
        return None
    path = entry.get("storage_key")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except OSError:
        return None
