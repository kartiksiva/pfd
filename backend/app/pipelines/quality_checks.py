from typing import Dict, List, Optional

from app.pipelines.document_generation import PDD_SECTION_ORDER


def run_quality_checks(
    pdd: Dict,
    sipoc: List[Dict],
    confidence: float,
    document_type: str = "pdd",
    source_facts: Optional[Dict] = None,
) -> Dict:
    flags = []
    assumptions = []
    source_facts = source_facts or {}

    if document_type == "pdd":
        missing_sections = [key for key in PDD_SECTION_ORDER if key not in pdd]
        if missing_sections:
            flags.append(
                {
                    "type": "missing_sections",
                    "path": "pdd",
                    "message": f"Missing PDD sections: {', '.join(missing_sections)}",
                }
            )
    else:
        if not pdd.get("document_control"):
            flags.append({"type": "missing_sections", "path": "sop.document_control", "message": "Missing SOP document control section."})
        if not pdd.get("quality_checks"):
            flags.append({"type": "missing_sections", "path": "sop.quality_checks", "message": "Missing SOP quality checks section."})

    if not pdd.get("steps"):
        flags.append({"type": "missing_steps", "path": "pdd.steps", "message": "No process steps found."})

    if not sipoc:
        flags.append({"type": "missing_sipoc", "path": "sipoc", "message": "No SIPOC rows generated."})

    if source_facts.get("sla_targets"):
        sop_slas = pdd.get("sla_and_performance_targets", []) if isinstance(pdd.get("sla_and_performance_targets"), list) else []
        if not sop_slas or all("needs review" in str(row.get("target", "")).lower() for row in sop_slas if isinstance(row, dict)):
            flags.append(
                {
                    "type": "lost_operational_facts",
                    "path": "document.sla_and_performance_targets",
                    "message": "Transcript-backed SLA facts were not preserved in the generated document.",
                }
            )

    if source_facts.get("volumes_or_frequency"):
        inputs = pdd.get("prerequisites_and_inputs", {}) if isinstance(pdd.get("prerequisites_and_inputs"), dict) else {}
        frequency_rows = inputs.get("input_documents_data", []) if isinstance(inputs.get("input_documents_data"), list) else []
        frequency_text = " ".join(str(row.get("frequency", "")) for row in frequency_rows if isinstance(row, dict)).lower()
        if not frequency_text or "needs review" in frequency_text:
            flags.append(
                {
                    "type": "lost_operational_facts",
                    "path": "document.prerequisites_and_inputs.input_documents_data.frequency",
                    "message": "Transcript-backed volume/frequency facts were not preserved in the generated document.",
                }
            )

    if source_facts.get("systems"):
        document_systems = set(str(item).strip().lower() for item in pdd.get("systems", []) if str(item).strip())
        tools = pdd.get("tools_and_systems_reference", []) if isinstance(pdd.get("tools_and_systems_reference"), list) else []
        document_systems.update(
            str(row.get("tool_system", "")).strip().lower()
            for row in tools
            if isinstance(row, dict) and str(row.get("tool_system", "")).strip()
        )
        missing_systems = [
            system for system in source_facts.get("systems", [])
            if str(system).strip().lower() not in document_systems
        ]
        if missing_systems:
            flags.append(
                {
                    "type": "lost_system_context",
                    "path": "document.systems",
                    "message": f"Transcript-backed systems missing from generated document: {', '.join(missing_systems[:4])}",
                }
            )

    if source_facts.get("pain_points"):
        opportunities = pdd.get("automation_opportunities", []) if isinstance(pdd.get("automation_opportunities"), list) else []
        if not opportunities:
            flags.append(
                {
                    "type": "lost_operational_facts",
                    "path": "document.automation_opportunities",
                    "message": "Transcript-backed pain points were not preserved in the generated document.",
                }
            )

    if source_facts.get("effort_data"):
        steps = pdd.get("steps", []) if isinstance(pdd.get("steps"), list) else []
        has_effort = any(
            isinstance(step, dict) and step.get("effort_minutes_min") and step.get("effort_minutes_max")
            for step in steps
        )
        if not has_effort:
            flags.append(
                {
                    "type": "lost_operational_facts",
                    "path": "document.steps.effort",
                    "message": "Transcript-backed effort data was not preserved in the generated document.",
                }
            )

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
