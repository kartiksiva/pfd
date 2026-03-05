from typing import Dict, List


def _infer_role(summary: str) -> str:
    text = summary.lower()
    if "customer" in text:
        return "customer"
    if "validate" in text or "approve" in text:
        return "analyst"
    if "system" in text or "ui" in text:
        return "system"
    return "operator"


def _infer_system(summary: str) -> str:
    text = summary.lower()
    if "ticket" in text:
        return "ticketing_system"
    if "ui" in text or "screen" in text:
        return "web_application"
    return "manual_or_unspecified"


def _normalize_structured_extraction(structured: Dict, fallback_confidence: float) -> Dict:
    steps_in = structured.get("process_steps", [])
    process_steps: List[Dict] = []
    roles = set()
    systems = set()

    if isinstance(steps_in, list):
        for idx, item in enumerate(steps_in, start=1):
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary", "")).strip()
            role = str(item.get("role", "")).strip() or _infer_role(summary)
            system = str(item.get("system", "")).strip() or _infer_system(summary)
            roles.add(role)
            systems.add(system)
            process_steps.append(
                {
                    "step_no": int(item.get("step_no") or idx),
                    "title": str(item.get("title", "")).strip() or f"Step {idx}",
                    "summary": summary,
                    "sources": ["llm"],
                    "confidence": float(structured.get("confidence", fallback_confidence) or fallback_confidence),
                    "role": role,
                    "system": system,
                    "input": str(item.get("input", "process input")).strip() or "process input",
                    "output": str(item.get("output", summary)).strip() or summary,
                    "exception": str(item.get("exception", "")).strip(),
                }
            )

    process_steps = sorted(process_steps, key=lambda row: row["step_no"])
    handoffs = []
    for i in range(1, len(process_steps)):
        prev_role = process_steps[i - 1]["role"]
        curr_role = process_steps[i]["role"]
        if prev_role != curr_role:
            handoffs.append({"from_role": prev_role, "to_role": curr_role, "step_no": process_steps[i]["step_no"]})

    if not roles:
        roles = {row["role"] for row in process_steps}
    if not systems:
        systems = {row["system"] for row in process_steps}

    return {
        "process_steps": process_steps,
        "roles": sorted(list(roles)),
        "systems": sorted(list(systems)),
        "handoffs": handoffs,
        "process_name": str(structured.get("process_name", "")).strip() or "Analyzed Process",
        "purpose": str(structured.get("purpose", "")).strip() or "Document current process flow from submitted evidence.",
        "scope": str(structured.get("scope", "")).strip() or "Current-state process only.",
        "triggers": structured.get("triggers", []) if isinstance(structured.get("triggers"), list) else [],
        "preconditions": structured.get("preconditions", []) if isinstance(structured.get("preconditions"), list) else [],
        "business_rules": structured.get("business_rules", []) if isinstance(structured.get("business_rules"), list) else [],
        "exceptions": structured.get("exceptions", []) if isinstance(structured.get("exceptions"), list) else [],
        "outputs": structured.get("outputs", []) if isinstance(structured.get("outputs"), list) else [],
        "metrics": structured.get("metrics", []) if isinstance(structured.get("metrics"), list) else [],
        "risks": structured.get("risks", []) if isinstance(structured.get("risks"), list) else [],
        "sipoc": structured.get("sipoc", []) if isinstance(structured.get("sipoc"), list) else [],
        "confidence": float(structured.get("confidence", fallback_confidence) or fallback_confidence),
    }


def extract_process_structure(media_payload: Dict) -> Dict:
    structured = media_payload.get("structured_extraction")
    if isinstance(structured, dict) and structured.get("process_steps"):
        return _normalize_structured_extraction(structured, fallback_confidence=float(media_payload.get("confidence", 0.0)))

    merged_steps = media_payload.get("merged_steps", [])
    process_steps: List[Dict] = []
    roles = set()
    systems = set()

    for idx, item in enumerate(merged_steps, start=1):
        summary = item.get("summary", "").strip()
        role = _infer_role(summary)
        system = _infer_system(summary)
        roles.add(role)
        systems.add(system)
        process_steps.append(
            {
                "step_no": idx,
                "title": f"Step {idx}",
                "summary": summary,
                "sources": item.get("sources", []),
                "confidence": item.get("confidence", 0.0),
                "role": role,
                "system": system,
                "input": "process input",
                "output": summary,
                "exception": "",
            }
        )

    handoffs = []
    for i in range(1, len(process_steps)):
        prev_role = process_steps[i - 1]["role"]
        curr_role = process_steps[i]["role"]
        if prev_role != curr_role:
            handoffs.append({"from_role": prev_role, "to_role": curr_role, "step_no": process_steps[i]["step_no"]})

    return {
        "process_steps": process_steps,
        "roles": sorted(list(roles)),
        "systems": sorted(list(systems)),
        "handoffs": handoffs,
        "process_name": "Analyzed Process",
        "purpose": "Document current process flow from submitted evidence.",
        "scope": "Current-state process only.",
        "triggers": ["Process initiation event captured from evidence."],
        "preconditions": ["Relevant source material is available."],
        "business_rules": [],
        "exceptions": [],
        "outputs": [],
        "metrics": [],
        "risks": [],
        "sipoc": [],
        "confidence": media_payload.get("confidence", 0.0),
    }
