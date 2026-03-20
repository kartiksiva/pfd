import re
from typing import Dict, List

from app.transcript_utils import normalize_transcript_text


INTERNAL_ACTION_LABELS = {
    "segment_process_frames",
    "infer_activity_timeline",
    "extract_steps",
    "detect_visual_handoffs",
    "extract_spoken_steps",
}
VTT_NOISE_PATTERNS = [
    re.compile(r"^webvtt$", flags=re.IGNORECASE),
    re.compile(r"^\d+$"),
    re.compile(r"^\d{2,}:\d{2}(?::\d{2})?\.\d{3}\s+-->\s+\d{2,}:\d{2}(?::\d{2})?\.\d{3}(?:\s+.*)?$", flags=re.IGNORECASE),
]
TRANSCRIPT_MARKDOWN_NOISE_PATTERNS = [
    re.compile(r"^#+\s+.*$"),
    re.compile(r"^\*\*[\d:]+\s*-\s*[\d:]+\*\*$"),
    re.compile(r"^(session overview|participants|transcript)$", flags=re.IGNORECASE),
]
STEP_NOISE_PATTERNS = [
    re.compile(r"^webvtt$", flags=re.IGNORECASE),
    re.compile(r"^\d+$"),
    re.compile(r"^\d{2}:\d{2}(?::\d{2})?$"),
    re.compile(r"^\d{2}:\d{2}(?::\d{2})?\.\d{3}$"),
    re.compile(r"^\d{2}:\d{2}(?::\d{2})?\s*-->\s*\d{2}:\d{2}(?::\d{2})?$", flags=re.IGNORECASE),
    re.compile(r"^\d{2}:\d{2}(?::\d{2})?\.\d{3}\s*-->\s*\d{2}:\d{2}(?::\d{2})?\.\d{3}(?:\s+.*)?$", flags=re.IGNORECASE),
]
SPEAKER_LABEL_RE = re.compile(
    r"^(?:\*{0,2})?(?:[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.&()/:-]+){0,5})(?:\s*\([^)]+\))?\s*:\s*"
)


def _is_vtt_noise(text: str) -> bool:
    cleaned = str(text or "").strip()
    return any(pattern.fullmatch(cleaned) for pattern in VTT_NOISE_PATTERNS)


def _is_internal_action_label(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if normalized in INTERNAL_ACTION_LABELS:
        return True
    return bool(re.fullmatch(r"[a-z]+(?:_[a-z0-9]+){1,6}", normalized))


def _normalize_step_summary(summary: str, source: str = "") -> str:
    cleaned = summary.strip()
    if not cleaned:
        return ""
    if _is_vtt_noise(cleaned):
        return ""
    if not _is_internal_action_label(cleaned):
        return cleaned

    source_key = source.strip().lower()
    if source_key == "video":
        return "Review the on-screen workflow segment and confirm the business action."
    if source_key == "audio":
        return "Review the narrated activity and confirm the business step."
    if source_key == "transcript":
        return "Review the transcript excerpt and confirm the business step."
    if source_key == "llm":
        return ""
    return "Review the captured evidence and confirm the business step."


def _normalize_step_title(title: str, idx: int, summary: str) -> str:
    cleaned = title.strip()
    if cleaned and not re.fullmatch(r"Step\s+\d+", cleaned, flags=re.IGNORECASE):
        return cleaned
    if summary:
        short = summary[:60].strip()
        return short if len(summary) <= 60 else short.rstrip() + "..."
    return f"Step {idx}"


def _infer_role(summary: str) -> str:
    text = summary.lower()
    if "customer" in text:
        return "customer"
    if "analyst" in text:
        complaint_markers = [
            "complaint",
            "crm",
            "shared mailbox",
            "phone log",
            "categor",
            "assign",
            "triage",
            "acknowledg",
        ]
        if any(marker in text for marker in complaint_markers):
            return "customer_service_analyst"
        return "analyst"
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


def _dedupe_preserve(values: List[str]) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _merge_unique(base: List[str], additions: List[str]) -> List[str]:
    return _dedupe_preserve([*(base or []), *(additions or [])])


def _clean_sentence(text: str) -> str:
    cleaned = " ".join(str(text or "").split())
    return cleaned.strip(" .")


def _clean_transcript_segment(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if _is_vtt_noise(cleaned) or any(pattern.fullmatch(cleaned) for pattern in TRANSCRIPT_MARKDOWN_NOISE_PATTERNS):
        return ""
    cleaned = re.sub(r"^\*\*[\d:]+\s*-\s*[\d:]+\*\*\s*", "", cleaned)
    cleaned = re.sub(r"^\s*[-*]\s*", "", cleaned)
    for _ in range(3):
        updated = SPEAKER_LABEL_RE.sub("", cleaned, count=1)
        if updated == cleaned:
            break
        cleaned = updated.strip()
    cleaned = _clean_sentence(cleaned)
    if any(pattern.fullmatch(cleaned) for pattern in STEP_NOISE_PATTERNS):
        return ""
    return cleaned


def _normalized_transcript_text(transcript_text: str, transcript_format: str = "") -> str:
    format_hint = str(transcript_format or "").strip().lower()
    filename = "transcript.vtt" if format_hint == "webvtt" else ""
    normalized = normalize_transcript_text(str(transcript_text or ""), filename=filename)
    return normalized.text if normalized.text else str(transcript_text or "")


def _sentence_windows(transcript_text: str) -> List[str]:
    windows = []
    for block in re.split(r"\n\s*\n", transcript_text or ""):
        lines = [line.strip() for line in str(block).splitlines() if line.strip()]
        if not lines:
            candidate = _clean_transcript_segment(block)
            if not candidate:
                continue
            windows.append(candidate)
            continue
        for line in lines:
            candidate = _clean_transcript_segment(line)
            if not candidate:
                continue
            windows.append(candidate)
    return windows


def _looks_like_transcript_markdown(transcript_text: str) -> bool:
    text = str(transcript_text or "")
    if not text.strip():
        return False
    markers = [
        "# Process Discovery Session Transcript",
        "## Session Overview",
        "## Participants",
        "## Transcript",
        "**00:00 - 05:00**",
    ]
    hits = sum(1 for marker in markers if marker in text)
    return hits >= 2


def _looks_like_raw_webvtt(transcript_text: str) -> bool:
    text = str(transcript_text or "")
    if not text.strip():
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    if lines[0] == "WEBVTT":
        return True
    timestamp_hits = sum(1 for line in lines if _is_vtt_noise(line) and "-->" in line)
    return timestamp_hits >= 2


def _contains_any(text: str, needles: List[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _is_future_state_window(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "future-state",
        "would it be acceptable",
        "we would also recommend",
        "recommend",
        "recommended future state",
        "proposed",
        "proposed automation",
        "ideally",
        "would be nice if",
        "would solve a lot",
        "automation candidate",
        "candidate for automation",
        "rules-based categorization suggestions",
        "assignment recommendations",
        "single intake queue",
        "automated reminders",
        "standardized acknowledgment templates",
        "common evidence checklist",
    ]
    return any(marker in lowered for marker in markers)


def _is_prompt_like_window(text: str) -> bool:
    lowered = text.lower().strip()
    prompts = [
        "tell me more about",
        "walk us through",
        "what causes this process to begin",
        "what happens if",
        "what systems are involved",
        "how do you handle",
        "how is work assigned",
        "based on what logic",
        "what's the next step",
        "lets start with the trigger",
        "let’s start with the trigger",
        "let’s validate the biggest pain points",
        "lets validate the biggest pain points",
        "approximately how many",
        "is the categorization based on a documented decision tree",
        "are assignment rules written anywhere",
        "would it be acceptable",
        "anything missing",
    ]
    return lowered.endswith("?") or any(prompt in lowered for prompt in prompts)


def _is_step_noise_fragment(text: str) -> bool:
    cleaned = _clean_transcript_segment(text)
    if not cleaned:
        return True
    lowered = cleaned.lower()
    if len(cleaned) < 5:
        return True
    if any(pattern.fullmatch(cleaned) for pattern in STEP_NOISE_PATTERNS):
        return True
    if "-->" in cleaned or lowered == "webvtt":
        return True
    if _is_prompt_like_window(cleaned) or _is_future_state_window(cleaned):
        return True
    return False


def _is_continuation_fragment(text: str) -> bool:
    cleaned = _clean_transcript_segment(text)
    if not cleaned:
        return False
    lowered = cleaned.lower()
    prefixes = (
        "and ",
        "but ",
        "then ",
        "also ",
        "there ",
        "for ",
        "if ",
        "after ",
        "because ",
        "which ",
        "provided ",
    )
    return cleaned[:1].islower() or lowered.startswith(prefixes)


def _sanitize_step_rows(process_steps: List[Dict]) -> List[Dict]:
    sanitized: List[Dict] = []
    for row in process_steps:
        title = _clean_transcript_segment(str(row.get("title", "")))
        summary = _clean_transcript_segment(str(row.get("summary", "")))
        if _is_step_noise_fragment(title) and _is_step_noise_fragment(summary):
            continue
        if _is_step_noise_fragment(summary):
            summary = title
        if _is_step_noise_fragment(title):
            title = summary[:60].strip() if summary else ""
        if not summary:
            continue
        if _is_prompt_like_window(summary) or _is_future_state_window(summary):
            continue
        cleaned = dict(row)
        cleaned["summary"] = summary
        cleaned["title"] = title or summary[:60]
        sanitized.append(cleaned)
    return sanitized


def _group_operational_steps(process_steps: List[Dict]) -> List[Dict]:
    if not process_steps:
        return []
    grouped: List[Dict] = []
    for row in process_steps:
        current = dict(row)
        if not grouped:
            grouped.append(current)
            continue
        previous = grouped[-1]
        same_role = str(previous.get("role", "")).strip().lower() == str(current.get("role", "")).strip().lower()
        same_system = str(previous.get("system", "")).strip().lower() == str(current.get("system", "")).strip().lower()
        if same_role and same_system and _is_continuation_fragment(str(current.get("summary", ""))):
            prev_summary = _clean_sentence(str(previous.get("summary", "")))
            curr_summary = _clean_sentence(str(current.get("summary", "")))
            if curr_summary and curr_summary.lower() not in prev_summary.lower():
                previous["summary"] = f"{prev_summary}. {curr_summary}".strip(". ")
                if str(previous.get("output", "")).strip().lower() in {"", "process input", prev_summary.lower()}:
                    previous["output"] = previous["summary"]
            continue
        grouped.append(current)
    for idx, row in enumerate(grouped, start=1):
        row["step_no"] = idx
    return grouped


def _derive_generic_triggers(transcript_text: str, extraction: Dict) -> List[str]:
    triggers = []
    transcript_lower = transcript_text.lower()
    channel_map = {
        "email": "Input received via email.",
        "web form": "Input received via web form.",
        "portal": "Input received via portal.",
        "phone": "Input received via phone.",
        "excel": "Input received from spreadsheet or workbook.",
        "spreadsheet": "Input received from spreadsheet or workbook.",
        "upload": "Input received through an upload step.",
    }
    for needle, label in channel_map.items():
        if needle in transcript_lower:
            triggers.append(label)

    if not triggers:
        steps = extraction.get("process_steps", []) if isinstance(extraction.get("process_steps"), list) else []
        first_input = ""
        if steps and isinstance(steps[0], dict):
            first_input = _clean_sentence(str(steps[0].get("input", "")))
        if first_input and first_input.lower() != "process input":
            triggers.append(f"Process starts when {first_input[0].lower() + first_input[1:]}.")
    return _dedupe_preserve(triggers)


def _derive_generic_outputs(transcript_text: str, extraction: Dict) -> List[str]:
    outputs = []
    steps = extraction.get("process_steps", []) if isinstance(extraction.get("process_steps"), list) else []
    for step in steps[-3:]:
        if not isinstance(step, dict):
            continue
        value = _clean_sentence(str(step.get("output", "")))
        if value and value.lower() not in {"", "needs review"}:
            outputs.append(value)

    transcript_lower = transcript_text.lower()
    hint_map = {
        "submitted": "Submission completed",
        "confirmation": "Completion confirmation recorded",
        "completed": "Process completion recorded",
        "report": "Process result report available",
    }
    for needle, label in hint_map.items():
        if needle in transcript_lower:
            outputs.append(label)
    return _dedupe_preserve(outputs)


def _derive_operational_facts(transcript_text: str, extraction: Dict) -> Dict:
    windows = _sentence_windows(transcript_text)
    facts = {
        "frequency": "",
        "volumes_or_frequency": [],
        "sla_targets": [],
        "routing_rules": [],
        "control_requirements": [],
        "governance_notes": [],
        "quantified_pain_points": [],
        "systems": [],
        "teams": [],
        "exception_details": [],
    }
    if not windows:
        return facts

    systems = []
    system_patterns = {
        "Outlook": ["outlook", "shared mailbox"],
        "Excel": ["excel", "spreadsheet", "tracking spreadsheet", "phone log"],
        "CRM": ["crm"],
        "Customer support portal": ["customer support portal", "portal complaints", "portal"],
        "Web form": ["web form"],
        "Document repository": ["document repository"],
        "ERP": ["erp"],
    }
    teams = []
    team_patterns = {
        "Customer Service Analyst": ["analyst", "analysts"],
        "Call Center Agent": ["call team", "call center", "phone complaints are manually documented"],
        "Billing Operations": ["billing operations"],
        "Product Support": ["product support"],
        "Field Service": ["field service"],
        "Compliance Team": ["compliance"],
        "Management": ["management"],
    }

    for window in windows:
        if _is_future_state_window(window) or _is_prompt_like_window(window):
            continue
        lowered = window.lower()
        for system_name, needles in system_patterns.items():
            if _contains_any(lowered, needles):
                systems.append(system_name)
        for team_name, needles in team_patterns.items():
            if _contains_any(lowered, needles):
                teams.append(team_name)

        if re.search(r"\b\d+\s*(?:to|-)\s*\d+\s+per day\b", lowered):
            facts["volumes_or_frequency"].append(window)
            if not facts["frequency"]:
                facts["frequency"] = "Daily"
        if any(term in lowered for term in ["mondays", "product releases", "per day on average"]):
            facts["volumes_or_frequency"].append(window)
            if not facts["frequency"]:
                facts["frequency"] = "Daily"

        if "within 24 hours" in lowered or "business days" in lowered:
            facts["sla_targets"].append(window)
        if any(term in lowered for term in ["audit trail", "regulatory response timelines", "compliance standpoint", "retention requirements"]):
            facts["control_requirements"].append(window)
            facts["governance_notes"].append(window)

        if any(term in lowered for term in ["complaint type", "product line", "region", "customer tier", "strategic customers", "escalated accounts", "copied to compliance"]):
            facts["routing_rules"].append(window)
        if any(term in lowered for term in ["missing", "misclass", "wrong team", "bounce around", "does not respond", "other category", "attachments come in different formats"]):
            facts["exception_details"].append(window)
        if re.search(r"\b\d+\s*percent\b", lowered) or re.search(r"\b\d+\s*(?:to|-)\s*\d+\s+minutes?\b", lowered) or "high-volume" in lowered:
            facts["quantified_pain_points"].append(window)

    facts["systems"] = _dedupe_preserve([*systems, *extraction.get("systems", [])])
    facts["teams"] = _dedupe_preserve([*teams, *extraction.get("roles", [])])
    for key in (
        "volumes_or_frequency",
        "sla_targets",
        "routing_rules",
        "control_requirements",
        "governance_notes",
        "quantified_pain_points",
        "exception_details",
    ):
        facts[key] = _dedupe_preserve(facts[key])
    return facts


def _enrich_extraction_with_operational_facts(extraction: Dict, transcript_text: str) -> Dict:
    enriched = dict(extraction or {})
    facts = _derive_operational_facts(transcript_text, enriched)
    enriched["operational_facts"] = facts
    enriched["systems"] = _merge_unique(enriched.get("systems", []), facts.get("systems", []))
    enriched["roles"] = _merge_unique(enriched.get("roles", []), facts.get("teams", []))
    enriched["metrics"] = _merge_unique(
        enriched.get("metrics", []),
        facts.get("sla_targets", []) + facts.get("quantified_pain_points", []) + facts.get("volumes_or_frequency", []),
    )
    enriched["business_rules"] = _merge_unique(
        enriched.get("business_rules", []),
        facts.get("routing_rules", []) + facts.get("control_requirements", []),
    )
    enriched["exceptions"] = _merge_unique(enriched.get("exceptions", []), facts.get("exception_details", []))
    if not enriched.get("triggers"):
        enriched["triggers"] = _derive_generic_triggers(transcript_text, enriched)
    if not enriched.get("outputs"):
        enriched["outputs"] = _derive_generic_outputs(transcript_text, enriched)
    return enriched


def _normalize_structured_extraction(structured: Dict, fallback_confidence: float) -> Dict:
    steps_in = structured.get("process_steps", [])
    process_steps: List[Dict] = []
    roles = set()
    systems = set()

    if isinstance(steps_in, list):
        for idx, item in enumerate(steps_in, start=1):
            if not isinstance(item, dict):
                continue
            summary = _normalize_step_summary(str(item.get("summary", "")), "llm")
            if not summary:
                continue
            role = str(item.get("role", "")).strip() or _infer_role(summary)
            system = str(item.get("system", "")).strip() or _infer_system(summary)
            roles.add(role)
            systems.add(system)
            process_steps.append(
                {
                    "step_no": int(item.get("step_no") or idx),
                    "title": _normalize_step_title(str(item.get("title", "")), idx, summary),
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
    process_steps = _group_operational_steps(_sanitize_step_rows(process_steps))
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
        "decision_rules": structured.get("decision_rules", []) if isinstance(structured.get("decision_rules"), list) else [],
        "effort_data": structured.get("effort_data", []) if isinstance(structured.get("effort_data"), list) else [],
        "pain_points": structured.get("pain_points", []) if isinstance(structured.get("pain_points"), list) else [],
        "sipoc": structured.get("sipoc", []) if isinstance(structured.get("sipoc"), list) else [],
        "confidence": float(structured.get("confidence", fallback_confidence) or fallback_confidence),
        "operational_facts": structured.get("operational_facts", {}) if isinstance(structured.get("operational_facts"), dict) else {},
    }


def extract_process_structure(media_payload: Dict) -> Dict:
    transcript_text = _normalized_transcript_text(
        str(media_payload.get("transcript_text", "") or ""),
        transcript_format=str(media_payload.get("transcript_format", "") or ""),
    )
    structured = media_payload.get("structured_extraction")
    if isinstance(structured, dict) and structured.get("process_steps"):
        normalized = _normalize_structured_extraction(structured, fallback_confidence=float(media_payload.get("confidence", 0.0)))
        return _enrich_extraction_with_operational_facts(normalized, transcript_text)

    if _looks_like_transcript_markdown(transcript_text):
        base = {
            "process_steps": [],
            "roles": [],
            "systems": [],
            "handoffs": [],
            "process_name": "Analyzed Process",
            "purpose": "Structured extraction was unavailable for the uploaded transcript and requires review.",
            "scope": "Current-state process only.",
            "triggers": ["Transcript review requires structured extraction to identify the process boundary."],
            "preconditions": ["Relevant source material is available."],
            "business_rules": [],
            "exceptions": [],
            "outputs": [],
            "metrics": [],
            "risks": [],
            "decision_rules": [],
            "effort_data": [],
            "pain_points": [],
            "sipoc": [],
            "confidence": 0.0,
        }
        return _enrich_extraction_with_operational_facts(base, transcript_text)

    merged_steps = media_payload.get("merged_steps", [])
    process_steps: List[Dict] = []
    roles = set()
    systems = set()

    for idx, item in enumerate(merged_steps, start=1):
        source = ""
        if isinstance(item.get("sources"), list) and item.get("sources"):
            source = str(item["sources"][0])
        summary = _normalize_step_summary(str(item.get("summary", "")), source)
        if not summary:
            continue
        role = _infer_role(summary)
        system = _infer_system(summary)
        roles.add(role)
        systems.add(system)
        process_steps.append(
            {
                "step_no": len(process_steps) + 1,
                "title": _normalize_step_title("", len(process_steps) + 1, summary),
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
    process_steps = _group_operational_steps(_sanitize_step_rows(process_steps))

    handoffs = []
    for i in range(1, len(process_steps)):
        prev_role = process_steps[i - 1]["role"]
        curr_role = process_steps[i]["role"]
        if prev_role != curr_role:
            handoffs.append({"from_role": prev_role, "to_role": curr_role, "step_no": process_steps[i]["step_no"]})

    base = {
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
        "decision_rules": [],
        "effort_data": [],
        "pain_points": [],
        "sipoc": [],
        "confidence": media_payload.get("confidence", 0.0),
    }
    return _enrich_extraction_with_operational_facts(base, str(media_payload.get("transcript_text", "") or ""))
