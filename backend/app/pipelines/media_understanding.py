from typing import Dict, List, Optional

from app.pipelines.frame_selector import select_key_frames


def _split_transcript_into_steps(transcript_text: str) -> List[Dict]:
    if not transcript_text:
        return []
    raw_parts = []
    for line in transcript_text.splitlines():
        line = line.strip()
        if not line:
            continue
        raw_parts.extend([p.strip() for p in line.split(".") if p.strip()])
    steps = []
    for idx, text in enumerate(raw_parts, start=1):
        steps.append({"step_no": idx, "text": text, "source": "transcript"})
    return steps


def _derive_confidence(visual_events: List[Dict], process_candidates: List[Dict], transcript_steps: List[Dict]) -> float:
    visual_scores = [float(v.get("confidence", 0.0)) for v in visual_events if "confidence" in v]
    visual_avg = (sum(visual_scores) / len(visual_scores)) if visual_scores else 0.0
    candidate_score = min(len(process_candidates) * 0.1, 0.4)
    transcript_score = min(len(transcript_steps) * 0.05, 0.4)
    total = min(visual_avg * 0.4 + candidate_score + transcript_score, 0.95)
    return round(total, 2)


def _merge_signals(transcript_steps: List[Dict], visual_events: List[Dict], process_candidates: List[Dict]) -> List[Dict]:
    merged = []
    seen = set()

    for step in transcript_steps:
        key = step["text"].strip().lower()
        if key and key not in seen:
            merged.append({"summary": step["text"], "sources": ["transcript"], "confidence": 0.7})
            seen.add(key)

    for candidate in process_candidates:
        summary = (candidate.get("summary") or candidate.get("action") or "").strip()
        if not summary:
            continue
        key = summary.lower()
        if key in seen:
            for row in merged:
                if row["summary"].strip().lower() == key:
                    source = candidate.get("source", "unknown")
                    if source not in row["sources"]:
                        row["sources"].append(source)
                        row["confidence"] = min(round(row["confidence"] + 0.05, 2), 0.95)
            continue
        merged.append(
            {
                "summary": summary,
                "sources": [candidate.get("source", "unknown")],
                "confidence": 0.68,
            }
        )
        seen.add(key)

    if visual_events:
        merged.append(
            {
                "summary": "Visual cues detected during process walkthrough.",
                "sources": ["video"],
                "confidence": 0.6,
            }
        )
    return merged


def build_media_understanding_payload(evidence: Dict, input_manifest: Optional[Dict] = None) -> Dict:
    transcript_text = evidence.get("transcript_text", "")
    visual_events = evidence.get("visual_events", [])
    process_candidates = evidence.get("process_candidates", [])
    frame_images = evidence.get("frame_images", []) or []
    structured_extraction = evidence.get("structured_extraction")
    key_frames = select_key_frames(input_manifest=input_manifest, evidence=evidence)

    transcript_steps = _split_transcript_into_steps(transcript_text)
    merged_steps = _merge_signals(transcript_steps, visual_events, process_candidates)
    confidence = _derive_confidence(visual_events, process_candidates, transcript_steps)

    return {
        "transcript_text": transcript_text,
        "transcript_steps": transcript_steps,
        "visual_events": visual_events,
        "key_frames": key_frames,
        "process_candidates": process_candidates,
        "frame_images": frame_images,
        "merged_steps": merged_steps,
        "structured_extraction": structured_extraction,
        "confidence": confidence,
    }
