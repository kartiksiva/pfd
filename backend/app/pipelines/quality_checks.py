from typing import Dict, List

from app.pipelines.document_generation import PDD_SECTION_ORDER


def run_quality_checks(pdd: Dict, sipoc: List[Dict], confidence: float) -> Dict:
    flags = []
    assumptions = []

    missing_sections = [key for key in PDD_SECTION_ORDER if key not in pdd]
    if missing_sections:
        flags.append(
            {
                "type": "missing_sections",
                "path": "pdd",
                "message": f"Missing PDD sections: {', '.join(missing_sections)}",
            }
        )

    if not pdd.get("steps"):
        flags.append({"type": "missing_steps", "path": "pdd.steps", "message": "No process steps found."})

    if not sipoc:
        flags.append({"type": "missing_sipoc", "path": "sipoc", "message": "No SIPOC rows generated."})

    if confidence < 0.5:
        flags.append(
            {
                "type": "low_confidence",
                "path": "evidence.confidence",
                "message": "Low extraction confidence; review required.",
            }
        )
        assumptions.append("Low-confidence extraction requires analyst review before finalization.")

    penalty = min(len(flags) * 0.12, 0.72)
    quality_score = max(round(confidence - penalty, 2), 0.05)
    return {"quality_score": quality_score, "flags": flags, "assumptions": assumptions}

