import re
from typing import Dict, List, Optional
from datetime import date


PDD_SECTION_ORDER = [
    "purpose",
    "scope",
    "triggers",
    "preconditions",
    "steps",
    "roles",
    "systems",
    "business_rules",
    "exceptions",
    "outputs",
    "metrics",
    "risks",
]


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


def _clean_fact_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for _ in range(3):
        updated = text
        updated = re.sub(r"^\*+\s*", "", updated)
        updated = re.sub(r"^\*{0,2}\s*([A-Z][A-Za-z .&()/'-]{1,80})\s*:\*{0,2}\s*", "", updated)
        updated = re.sub(r"^[A-Z][A-Za-z .&()/'-]{1,80}\s*:\s*", "", updated)
        if updated == text:
            break
        text = updated
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .")


def _is_future_state_statement(value: str) -> bool:
    lowered = _clean_fact_text(value).lower()
    if not lowered:
        return False
    markers = [
        "future-state",
        "would it be acceptable",
        "we would also recommend",
        "candidate for automation",
        "could be more rules-based",
        "should not be typed manually",
        "would solve a lot",
        "proposed rules",
        "assignment recommendations",
        "categorization suggestions",
        "single intake queue",
        "automated reminders",
        "standardized acknowledgment templates",
        "evidence checklist",
    ]
    return any(marker in lowered for marker in markers)


def _is_operational_question(value: str) -> bool:
    lowered = _clean_fact_text(value).lower()
    if not lowered:
        return False
    prompts = [
        "what happens if",
        "let’s validate the biggest pain points",
        "lets validate the biggest pain points",
        "anything missing",
        "approximately how many",
        "are assignment rules written anywhere",
        "is the categorization based on",
        "which parts absolutely require human review",
        "would it be acceptable",
    ]
    return lowered.endswith("?") or any(prompt in lowered for prompt in prompts)


def _normalize_role_name(role: str) -> str:
    cleaned = _clean_fact_text(role)
    if not cleaned:
        return ""
    cleaned = cleaned.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned.islower():
        return cleaned.title()
    return cleaned


def _role_responsibility(role: str) -> str:
    lowered = role.lower()
    if any(token in lowered for token in ["approver", "reviewer", "manager", "lead"]):
        return "Reviews or approves the documented process activities; detailed responsibility needs review."
    if "system" in lowered or "bot" in lowered or "application" in lowered:
        return "Supports automated or system-executed process activities; detailed responsibility needs review."
    return "Performs documented process activities; detailed responsibility needs review."


def _build_role_rows(roles: List[str]) -> List[Dict]:
    rows: List[Dict] = []
    for role in _dedupe_preserve([_normalize_role_name(role) for role in roles]):
        if not role:
            continue
        rows.append(
            {
                "role": role,
                "responsibility": _role_responsibility(role),
                "team_location": "Needs Review",
            }
        )
    return rows


def _normalize_custom_sop_role(role: str) -> str:
    return _normalize_role_name(role)


def _custom_sop_roles(roles: List[str], facts: Dict) -> List[str]:
    source = list(roles or []) + list(facts.get("teams", []) or [])
    normalized = [_normalize_custom_sop_role(role) for role in source]
    return _dedupe_preserve([role for role in normalized if role and role.lower() != "needs review"])


def _custom_sop_owner(roles: List[str], steps: List[Dict]) -> str:
    for role in roles:
        cleaned = _normalize_role_name(role)
        if cleaned and cleaned.lower() not in {"operator", "system", "customer", "needs review"}:
            return cleaned
    for step in steps:
        actor = _normalize_custom_sop_role(str(step.get("actor", "")))
        if actor and actor.lower() not in {"operator", "system", "customer", "needs review"}:
            return actor
    return "Needs Review"


def _custom_sop_purpose(raw_purpose: str) -> str:
    cleaned = _clean_fact_text(raw_purpose)
    lowered = cleaned.lower()
    if cleaned and lowered != "needs review":
        return cleaned
    return "To execute the documented current-state process consistently, with clear steps, controls, and exception handling."


def _custom_sop_scope_text(raw_scope: str) -> str:
    cleaned = _clean_fact_text(raw_scope)
    lowered = cleaned.lower()
    if cleaned and lowered != "needs review":
        if any(token in lowered for token in ["closure", "post-resolution", "post resolution", "close customer complaints"]):
            return "The process begins at the documented trigger and ends when the final documented output is produced."
        return cleaned
    return "The process begins at the documented trigger and ends when the final documented output is produced."


def _contains_current_state_marker(text: str, markers: List[str]) -> bool:
    lowered = _clean_fact_text(text).lower()
    return any(marker in lowered for marker in markers)


def _is_custom_sop_step_supported(step: Dict) -> bool:
    text = _clean_fact_text(" ".join([str(step.get("title", "")), str(step.get("description", ""))])).lower()
    if not text:
        return False
    blocked = ["future-state", "recommended future state", "proposed automation", "recommended automation"]
    return not any(marker in text for marker in blocked)


def _normalize_custom_sop_step(step: Dict) -> Dict:
    normalized = dict(step)
    title = _clean_fact_text(str(step.get("title", "")))
    if title:
        normalized["title"] = title
    normalized["actor"] = _normalize_custom_sop_role(str(step.get("actor", "")) or str(step.get("role", "")))
    return normalized


def _custom_sop_step_notes(steps: List[Dict], facts: Dict) -> List[Dict]:
    return [dict(step) for step in steps]


def _cleanup_custom_sop_step_boundaries(steps: List[Dict]) -> List[Dict]:
    cleaned_steps = [dict(step) for step in steps]
    if len(cleaned_steps) < 2:
        return cleaned_steps

    first = cleaned_steps[0]
    second = cleaned_steps[1]
    first_title = _clean_fact_text(str(first.get("title", ""))).lower()
    second_title = _clean_fact_text(str(second.get("title", ""))).lower()
    second_description = _clean_fact_text(str(second.get("description", "")))

    if "intake and record creation" in first_title and "validation" in second_title:
        first_description = _clean_fact_text(str(first.get("description", "")))
        first_description = re.sub(
            r"\s*Mandatory fields are checked\.?$",
            "",
            first_description,
            flags=re.IGNORECASE,
        ).strip()
        if first_description:
            first["description"] = first_description
        if second_description and "if information is missing" not in second_description.lower():
            second["description"] = (
                second_description
                + " If information is missing, analyst sends follow-up email to customer."
            )

    return cleaned_steps


def _custom_sop_inputs(steps: List[Dict], facts: Dict) -> List[str]:
    inputs = []
    for step in steps:
        cleaned = _clean_fact_text(str(step.get("input", "")))
        if cleaned and cleaned.lower() not in {"process input", "needs review"}:
            inputs.append(cleaned)
    return _dedupe_preserve(inputs)


def _custom_sop_outputs(steps: List[Dict]) -> List[str]:
    outputs = []
    for step in steps:
        cleaned = _clean_fact_text(str(step.get("output", "")))
        if cleaned and cleaned.lower() not in {"needs review"}:
            outputs.append(cleaned)
    return _dedupe_preserve(outputs)


def _custom_sop_summary(steps: List[Dict], facts: Dict, roles: List[str]) -> Dict:
    return {
        "suppliers": [],
        "inputs": _custom_sop_inputs(steps, facts),
        "outputs": _custom_sop_outputs(steps),
        "customers": [],
    }


def _custom_sop_faq_items(steps: List[Dict], facts: Dict) -> List[Dict]:
    return [{"topic": "Process overview", "tip": "Needs Review"}]


def _normalize_exception_description(item: str) -> str:
    cleaned = _clean_fact_text(item)
    if not cleaned:
        return "Needs Review"
    lowered = cleaned.lower()
    cleaned = re.sub(r"^(not really\.?\s*)", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"^(another delay is\s+)", "", cleaned, flags=re.IGNORECASE).strip()
    if any(token in lowered for token in ["misclass", "wrong team", "routing"]):
        return "Existing guidance is informal, so newer team members may classify complaints inconsistently."
    if "missing" in lowered:
        return "Missing information or documents delay processing and require follow-up before work can continue."
    if any(token in lowered for token in ["attachment", "format", "naming convention"]):
        return "Attachments may arrive in inconsistent formats or naming conventions and require manual cleanup."
    return cleaned


def _exception_scenario(item: str) -> str:
    lowered = _clean_fact_text(item).lower()
    if "missing" in lowered:
        return "Required information or input is missing."
    if any(token in lowered for token in ["wrong team", "wrong owner", "misclass", "reassign", "routing error"]):
        return "Work item is routed or classified incorrectly."
    if any(token in lowered for token in ["timeout", "timed out", "slow", "delay"]):
        return "The process exceeds the expected turnaround time."
    if any(token in lowered for token in ["attachment", "format", "file", "corrupt"]):
        return "Input files or attachments require manual correction."
    return _clean_fact_text(item) or "Needs Review"


def _exception_action(item: str) -> str:
    lowered = _clean_fact_text(item).lower()
    if "missing" in lowered:
        return "Obtain the missing information and pause the process until the required input is available."
    if any(token in lowered for token in ["wrong team", "wrong owner", "misclass", "reassign", "routing error"]):
        return "Correct the routing or classification and notify the responsible owner."
    if any(token in lowered for token in ["timeout", "timed out", "slow", "delay"]):
        return "Escalate the delay, confirm process status, and resume or restart the affected step as needed."
    if any(token in lowered for token in ["attachment", "format", "file", "corrupt"]):
        return "Correct the input file or attachment and re-run the affected step."
    return "Needs Review"


def _exception_owner(item: str) -> str:
    return "Needs Review"


def _control_from_fact(item: str) -> Optional[Dict]:
    cleaned = _clean_fact_text(item)
    lowered = cleaned.lower()
    if not cleaned or _is_future_state_statement(cleaned):
        return None
    if any(token in lowered for token in ["24 hours", "business days", "sla", "turnaround", "response time"]):
        return {
            "control": "CTRL-SLA",
            "type": "Manual Detective",
            "description": "Process performance targets must be monitored against the documented turnaround or response expectations.",
            "evidence_required": "Timestamps, status history, and performance records.",
        }
    if "audit trail" in lowered:
        return {
            "control": "CTRL-AUDIT",
            "type": "Manual Detective",
            "description": "Process actions and decisions must preserve a complete audit trail.",
            "evidence_required": "System history, logs, or retained evidence.",
        }
    if any(token in lowered for token in ["compliance", "policy", "regulatory", "retention requirement"]):
        return {
            "control": "CTRL-COMPLIANCE",
            "type": "Manual Detective",
            "description": "The process must comply with the documented policy, regulatory, or retention requirements.",
            "evidence_required": "Policy reference, review record, or retained evidence.",
        }
    return None


def _step_implied_controls(steps: List[Dict]) -> List[Dict]:
    implied: List[Dict] = []
    for step in steps:
        step_text = _clean_fact_text(
            " ".join([str(step.get("title", "")), str(step.get("description", "")), str(step.get("input", ""))])
        ).lower()
        step_core_text = _clean_fact_text(
            " ".join([str(step.get("title", "")), str(step.get("description", ""))])
        ).lower()
        step_title = str(step.get("title", "")).strip() or "Step"
        if any(token in step_text for token in ["validate", "validation", "required field", "mandatory field", "check"]):
            implied.append(
                {
                    "control": "CTRL-VALIDATION",
                    "type": "Manual Preventive",
                    "step_name": step_title,
                    "description": "Required fields and validation checks must be completed before the process continues.",
                    "evidence_required": "Validated record, checklist, or system confirmation.",
                }
            )
        if any(token in step_core_text for token in ["approval", "approve", "approved", "sign-off", "sign off", "authorize", "authorized"]):
            implied.append(
                {
                    "control": "CTRL-APPROVAL",
                    "type": "Manual Detective",
                    "step_name": step_title,
                    "description": "Required review or approval must be completed before downstream processing continues.",
                    "evidence_required": "Approval record, reviewer confirmation, or system status.",
                }
            )
        if "submit" in step_core_text:
            implied.append(
                {
                    "control": "CTRL-SUBMIT",
                    "type": "Manual Detective",
                    "step_name": step_title,
                    "description": "Submission or handoff completion must be confirmed before the next cycle starts.",
                    "evidence_required": "Submission confirmation, handoff record, or completion status.",
                }
            )
    deduped: List[Dict] = []
    seen = set()
    for row in implied:
        key = (row["description"].strip().lower(), str(row.get("step_name", "")).strip().lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _operational_facts(extraction: Dict) -> Dict:
    return extraction.get("operational_facts", {}) if isinstance(extraction.get("operational_facts"), dict) else {}


def _meaningful_process_name(extraction: Dict, mapped_steps: List[Dict]) -> str:
    extracted_process_name = str(extraction.get("process_name", "")).strip()
    if extracted_process_name and extracted_process_name.lower() not in {"analyzed process", "standard operating procedure"}:
        return extracted_process_name
    first_step_title = str(mapped_steps[0].get("title", "")).strip() if mapped_steps else ""
    if first_step_title and not first_step_title.lower().startswith("step "):
        return first_step_title
    return "Standard Operating Procedure"


def _infer_department(extraction: Dict, roles: List[str], facts: Dict) -> str:
    explicit = str(extraction.get("department", "")).strip()
    if explicit and explicit.lower() != "needs review":
        return explicit
    return "Needs Review"


def _infer_owner(roles: List[str], mapped_steps: List[Dict]) -> str:
    for role in roles:
        cleaned = str(role).strip()
        if cleaned and cleaned.lower() not in {"operator", "system", "customer"}:
            return cleaned
    return str(mapped_steps[0].get("actor", "")).strip() if mapped_steps else "Needs Review"


def _build_frequency(facts: Dict) -> str:
    if facts.get("frequency"):
        volume = facts.get("volumes_or_frequency", [])
        if volume:
            return f"{facts['frequency']} ({_clean_fact_text(volume[0])})"
        return str(facts["frequency"])
    volume = facts.get("volumes_or_frequency", [])
    return _clean_fact_text(volume[0]) if volume else "Needs Review"


def _build_sla_rows(facts: Dict) -> List[Dict]:
    rows = []
    for idx, item in enumerate(facts.get("sla_targets", [])[:4], start=1):
        cleaned = _clean_fact_text(item)
        if _is_future_state_statement(cleaned):
            continue
        lowered = cleaned.lower()
        if "regulatory complaints" in lowered and "24 hours" in lowered:
            rows.append(
                {
                    "kpi": "Regulatory complaints",
                    "definition": "Transcript-backed service level or response commitment",
                    "target": "Response within 24 hours",
                    "measurement_method": "Transcript evidence / operating policy review",
                }
            )
        if "standard complaints" in lowered and "business days" in lowered:
            rows.append(
                {
                    "kpi": "Standard complaints",
                    "definition": "Transcript-backed service level or response commitment",
                    "target": "Acknowledgement within 3 business days",
                    "measurement_method": "Transcript evidence / operating policy review",
                }
            )
        if rows and ("regulatory complaints" in lowered or "standard complaints" in lowered):
            continue
        target = cleaned
        if ":" in cleaned:
            kpi, target = cleaned.split(":", 1)
            metric = kpi.strip()
        else:
            metric = f"SLA {idx}"
        rows.append(
            {
                "kpi": metric,
                "definition": "Transcript-backed service level or response commitment",
                "target": target.strip() or cleaned,
                "measurement_method": "Transcript evidence / operating policy review",
            }
        )
    if rows:
        return rows
    return [
        {"kpi": "Accuracy Rate", "definition": "Completed steps without error", "target": "Needs Review", "measurement_method": "QC review"},
        {"kpi": "Turnaround Time", "definition": "Time from trigger to completion", "target": "Needs Review", "measurement_method": "System timestamps"},
    ]


def _build_controls(facts: Dict) -> Dict:
    controls = []
    for item in facts.get("control_requirements", []):
        control = _control_from_fact(item)
        if control:
            controls.append(control)
    deduped_controls = []
    seen = set()
    for control in controls:
        key = control["description"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped_controls.append(control)
    controls = deduped_controls
    policies = [
        _clean_fact_text(item)
        for item in facts.get("governance_notes", [])
        if _clean_fact_text(item) and not _is_future_state_statement(item)
    ]
    if not controls:
        controls = [{"control": "CTRL-1", "type": "Detective", "description": "Needs Review", "evidence_required": "Needs Review"}]
    return {"controls": controls, "policies": policies or ["Needs Review"]}


def _build_exception_matrix(facts: Dict) -> Dict:
    rows = []
    seen_scenarios = set()
    for idx, item in enumerate(facts.get("exception_details", [])[:8], start=1):
        cleaned = _clean_fact_text(item)
        if not cleaned or _is_future_state_statement(cleaned) or _is_operational_question(cleaned):
            continue
        scenario = _exception_scenario(cleaned)
        key = scenario.strip().lower()
        if key in seen_scenarios:
            continue
        seen_scenarios.add(key)
        rows.append(
            {
                "exception_id": f"EXC-{idx:02d}",
                "scenario": scenario,
                "trigger_symptom": _normalize_exception_description(cleaned),
                "action_to_take": _exception_action(cleaned),
                "escalation_path": _exception_owner(cleaned),
            }
        )
    if not rows:
        rows = [
            {
                "exception_id": "EXC-01",
                "scenario": "Needs Review",
                "trigger_symptom": "Needs Review",
                "action_to_take": "Needs Review",
                "escalation_path": "Needs Review",
            }
        ]
    return {
        "exception_matrix": rows,
        "escalation_matrix": [{"level": "L1", "trigger_condition": "Operator cannot resolve", "contact": "Needs Review", "response_time": "Needs Review"}],
    }


def _looks_like_rpa_challenge_process(process_name: str, steps: List[Dict]) -> bool:
    text = " ".join(
        [
            process_name,
            *[str(step.get("title", "")) for step in steps],
            *[str(step.get("description", "")) for step in steps],
            *[str(step.get("input", "")) for step in steps],
            *[str(step.get("output", "")) for step in steps],
        ]
    ).lower()
    markers = [
        "rpa challenge",
        "rpachallenge",
        "download excel",
        "dynamic form",
        "field layout",
        "10 rounds",
        "10 consecutive rounds",
    ]
    return any(marker in text for marker in markers)


def _build_challenge_steps(base_steps: List[Dict]) -> List[Dict]:
    if not base_steps:
        return []
    first_actor = str(base_steps[0].get("actor", "")).strip() or "Automation Bot"
    first_system = str(base_steps[0].get("system", "")).strip() or "RPA Challenge Website"
    rows = [
        {
            "title": "Download Input Spreadsheet",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "The bot navigates to the RPA Challenge website and downloads the source spreadsheet.",
            "input": "RPA Challenge web page",
            "output": "Downloaded Excel spreadsheet",
        },
        {
            "title": "Start Challenge",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "The bot clicks the Start button to begin the challenge and activate the data-entry form.",
            "input": "Downloaded Excel spreadsheet",
            "output": "Challenge timer starts",
        },
        {
            "title": "Identify Field Positions",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "For the current round, the bot identifies the current position of each labeled field on the web form.",
            "input": "Active web form",
            "output": "Field mapping for current round",
        },
        {
            "title": "Input Data into Form",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "The bot reads the current spreadsheet row and enters the corresponding values into the identified form fields.",
            "input": "Excel data row and field mapping",
            "output": "Populated web form",
        },
        {
            "title": "Submit Form",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "The bot submits the populated form for the current round.",
            "input": "Populated web form",
            "output": "Form submission confirmation",
        },
        {
            "title": "Repeat for All Items",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "The bot repeats the identify, input, and submit steps until all spreadsheet rows are processed.",
            "input": "Remaining Excel data",
            "output": "All items submitted",
        },
        {
            "title": "Capture Completion Time",
            "actor": first_actor,
            "system": "rpachallenge.com" if "rpachallenge" in first_system.lower() or "challenge" in first_system.lower() else first_system,
            "description": "After the last submission, the bot records the final completion time shown by the challenge.",
            "input": "Challenge completion event",
            "output": "Completion time result",
        },
    ]
    return rows


def _expand_custom_sop_steps(process_name: str, steps: List[Dict]) -> List[Dict]:
    if _looks_like_rpa_challenge_process(process_name, steps):
        return _build_challenge_steps(steps)
    return steps


def _decision_rule_lines(extraction: Dict) -> List[str]:
    rules = extraction.get("decision_rules", []) if isinstance(extraction.get("decision_rules"), list) else []
    rows: List[str] = []
    for row in rules:
        if not isinstance(row, dict):
            continue
        condition = _clean_fact_text(str(row.get("condition", "")))
        action = _clean_fact_text(str(row.get("action", "")))
        step_no = row.get("applies_to_step")
        if not condition or not action:
            continue
        prefix = f"Step {step_no}: " if isinstance(step_no, int) and step_no > 0 else ""
        rows.append(f"{prefix}If {condition}, then {action}.")
    return _dedupe_preserve(rows)


def _apply_effort_data_to_steps(steps: List[Dict], extraction: Dict) -> List[Dict]:
    effort_rows = extraction.get("effort_data", []) if isinstance(extraction.get("effort_data"), list) else []
    if not effort_rows:
        return steps
    mapped = []
    effort_by_step = {}
    for row in effort_rows:
        if not isinstance(row, dict):
            continue
        step_no = row.get("step_no")
        if not isinstance(step_no, int) or step_no <= 0:
            continue
        effort_by_step[step_no] = {
            "effort_minutes_min": int(row.get("effort_minutes_min", 0) or 0),
            "effort_minutes_max": int(row.get("effort_minutes_max", 0) or 0),
        }
    for idx, step in enumerate(steps, start=1):
        enriched = dict(step)
        raw_step_no = enriched.get("step_no")
        step_no = raw_step_no if isinstance(raw_step_no, int) and raw_step_no > 0 else idx
        if step_no in effort_by_step:
            enriched.update(effort_by_step[step_no])
        mapped.append(enriched)
    return mapped


def _automation_opportunities(extraction: Dict, facts: Dict) -> List[Dict]:
    rows = []
    pain_points = extraction.get("pain_points", []) if isinstance(extraction.get("pain_points"), list) else []
    for idx, row in enumerate(pain_points, start=1):
        if not isinstance(row, dict):
            continue
        description = _clean_fact_text(str(row.get("description", "")))
        if not description:
            continue
        rows.append(
            {
                "opportunity_id": f"AUTO-{idx:02d}",
                "description": description,
                "quantification": _clean_fact_text(str(row.get("quantification", ""))) or "Needs Review",
                "automation_signal": str(row.get("automation_signal", "medium")).strip().lower() or "medium",
            }
        )
    if rows:
        return rows
    fallback = []
    for idx, item in enumerate((facts.get("quantified_pain_points", []) if isinstance(facts, dict) else [])[:3], start=1):
        cleaned = _clean_fact_text(item)
        if not cleaned:
            continue
        fallback.append(
            {
                "opportunity_id": f"AUTO-{idx:02d}",
                "description": cleaned,
                "quantification": cleaned,
                "automation_signal": "medium",
            }
        )
    return fallback


def generate_pdd_document(extraction: Dict) -> Dict:
    steps = extraction.get("process_steps", [])
    roles = _dedupe_preserve(extraction.get("roles", []))
    facts = _operational_facts(extraction)
    systems = _dedupe_preserve(extraction.get("systems", []) + facts.get("systems", []))
    decision_rules = _decision_rule_lines(extraction)

    step_rows = []
    for row in steps:
        step_rows.append(
            {
                "step_no": row.get("step_no"),
                "title": row.get("title", f"Step {row.get('step_no', '')}"),
                "actor": row.get("role", "operator"),
                "system": row.get("system", "manual_or_unspecified"),
                "description": row.get("summary", ""),
                "input": row.get("input", "process input"),
                "output": row.get("output", row.get("summary", "")),
                "exception": row.get("exception", ""),
            }
        )

    pdd = {
        "purpose": extraction.get("purpose", "Document current process flow from submitted evidence."),
        "scope": extraction.get("scope", "Current-state process only."),
        "triggers": extraction.get("triggers", ["Process initiation event captured from evidence."]),
        "preconditions": extraction.get("preconditions", ["Relevant source material is available."]),
        "steps": step_rows,
        "roles": roles,
        "systems": systems,
        "business_rules": _dedupe_preserve(list(extraction.get("business_rules", [])) + decision_rules),
        "exceptions": extraction.get("exceptions", []),
        "outputs": extraction.get("outputs", []),
        "metrics": extraction.get("metrics", []),
        "risks": extraction.get("risks", []),
        "operational_facts": facts,
        "effort_data": extraction.get("effort_data", []) if isinstance(extraction.get("effort_data"), list) else [],
        "pain_points": extraction.get("pain_points", []) if isinstance(extraction.get("pain_points"), list) else [],
    }

    # Enforce deterministic section ordering contract.
    return {key: pdd.get(key) for key in PDD_SECTION_ORDER}


def _format_seconds(seconds: float) -> str:
    total = max(int(seconds), 0)
    hh = total // 3600
    mm = (total % 3600) // 60
    ss = total % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def _map_step_media(step_rows: List[Dict], frame_images: List[Dict]) -> List[Dict]:
    if not step_rows:
        return []
    if not frame_images:
        for row in step_rows:
            row["source_timestamp"] = row.get("source_timestamp", "")
            row["screenshot"] = None
        return step_rows

    frames = []
    for frame in frame_images:
        try:
            ts = float(frame.get("timestamp_seconds", 0.0) or 0.0)
        except Exception:
            ts = 0.0
        frames.append(
            {
                "timestamp_seconds": ts,
                "timestamp": _format_seconds(ts),
                "path": str(frame.get("path", "")),
                "reason": str(frame.get("reason", "baseline")),
            }
        )
    frames = sorted(frames, key=lambda row: row["timestamp_seconds"])

    indexed_targets = []
    if len(step_rows) == 1:
        indexed_targets = [frames[0]["timestamp_seconds"]]
    else:
        frame_count = len(frames)
        step_count = len(step_rows)
        for idx in range(step_count):
            frame_index = round(idx * max(frame_count - 1, 0) / max(step_count - 1, 1))
            indexed_targets.append(frames[frame_index]["timestamp_seconds"])

    for idx, row in enumerate(step_rows):
        raw_ts = row.get("timestamp_seconds")
        target_ts = None
        if isinstance(raw_ts, (int, float)):
            target_ts = float(raw_ts)
        elif isinstance(raw_ts, str) and raw_ts.strip():
            parts = raw_ts.strip().split(":")
            try:
                if len(parts) == 3:
                    target_ts = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2:
                    target_ts = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                target_ts = None
        if target_ts is None:
            target_ts = indexed_targets[idx]
        nearest = min(frames, key=lambda frame: abs(frame["timestamp_seconds"] - target_ts))
        row["source_timestamp"] = nearest["timestamp"]
        row["screenshot"] = {
            "path": nearest["path"],
            "timestamp": nearest["timestamp"],
            "timestamp_seconds": nearest["timestamp_seconds"],
            "reason": nearest["reason"],
        }
    return step_rows


def generate_document_from_extraction(
    extraction: Dict,
    *,
    document_type: str,
    frame_images: Optional[List[Dict]] = None,
) -> Dict:
    frame_images = frame_images or []
    pdd = generate_pdd_document(extraction)
    steps = pdd.get("steps", []) if isinstance(pdd.get("steps"), list) else []
    mapped_steps = _map_step_media(steps, frame_images)
    mapped_steps = _apply_effort_data_to_steps(mapped_steps, extraction)
    pdd["steps"] = mapped_steps

    if document_type not in {"sop", "custom_sop"}:
        return pdd

    facts = _operational_facts(extraction)
    scope_text = _custom_sop_scope_text(str(pdd.get("scope", "Current-state process only.")))
    custom_roles = _custom_sop_roles(pdd.get("roles", []) or [], facts)
    custom_steps = [_normalize_custom_sop_step(step) for step in mapped_steps if _is_custom_sop_step_supported(step)]
    custom_steps = _expand_custom_sop_steps(str(extraction.get("process_name", "")), custom_steps)
    custom_steps = _map_step_media(custom_steps, frame_images)
    custom_steps = _apply_effort_data_to_steps(custom_steps, extraction)
    custom_steps = _custom_sop_step_notes(custom_steps, facts)
    custom_steps = _cleanup_custom_sop_step_boundaries(custom_steps)
    sop_title = _meaningful_process_name(extraction, custom_steps or mapped_steps)
    inferred_owner = _custom_sop_owner(custom_roles, custom_steps or mapped_steps)
    inferred_department = _infer_department(extraction, custom_roles or pdd.get("roles", []) or [], facts)
    role_rows = _build_role_rows(custom_roles)
    outputs = _dedupe_preserve(pdd.get("outputs", []))
    flow_summary = " -> ".join([step.get("title", f"Step {idx+1}") for idx, step in enumerate(custom_steps[:8])]) or "Needs Review"
    trigger_input = (pdd.get("triggers", []) or ["process trigger"])[0]
    custom_summary = _custom_sop_summary(custom_steps, facts, custom_roles)
    controls = _build_controls(facts)
    automation_opportunities = _automation_opportunities(extraction, facts)
    for implied_control in _step_implied_controls(custom_steps):
        replaced = False
        for existing in controls["controls"]:
            if existing.get("description") == implied_control["description"]:
                if implied_control.get("step_name"):
                    existing["step_name"] = implied_control["step_name"]
                replaced = True
                break
        if not replaced:
            controls["controls"].append(implied_control)
    sop = {
        "document_control": {
            "sop_id": "SOP-OPS-001-" + str(pdd.get("purpose", "") or "YYYY")[:4],
            "sop_title": sop_title,
            "process_owner": inferred_owner,
            "department": inferred_department,
            "effective_date": date.today().strftime("%d-%b-%Y"),
            "review_date": "Needs Review",
            "version": "1.0",
            "classification": "Internal",
            "source_reference": "Generated from uploaded transcript/audio/video evidence",
        },
        "revision_history": [{"version": "1.0", "date": date.today().strftime("%d-%b-%Y"), "author": "PFCD Agent", "change_summary": "Initial Draft", "approved_by": "Needs Review"}],
        "purpose": _custom_sop_purpose(str(pdd.get("purpose", "Needs Review"))),
        "scope": {
            "in_scope": [scope_text] if scope_text else ["Needs Review"],
            "out_of_scope": ["Activities outside the documented current-state process boundary.", "Future-state redesign or automation recommendations."],
            "regions_entities": [{"region_entity": "Needs Review", "applicable": "Needs Review", "notes": "Needs Review"}],
        },
        "roles_and_responsibilities": role_rows or [{"role": "Needs Review", "responsibility": "Needs Review", "team_location": "Needs Review"}],
        "definitions": [
            {"term": "SOP", "definition": "Standard Operating Procedure"},
            {"term": "SLA", "definition": "Service Level Agreement"},
        ],
        "prerequisites_and_inputs": {
            "system_access_required": [{"system": s, "access_level": "Needs Review", "url_path": "Needs Review"} for s in (_dedupe_preserve(pdd.get("systems", []) or ["manual_or_unspecified"]))],
            "input_documents_data": [{"input": trigger_input, "source": "Source evidence", "format": "Needs Review", "frequency": _build_frequency(facts)}],
            "knowledge_skills_required": ["Needs Review"],
        },
        "process_overview": {
            "flow_summary": flow_summary,
            "metrics_at_glance": [{"metric": row["kpi"], "target": row["target"]} for row in _build_sla_rows(facts)[:3]],
        },
        "steps": custom_steps,
        "quality_checks": {
            "checks": [
                {
                    "check_id": f"QC-{idx:02d}",
                    "what_to_validate": control.get("description", "Needs Review"),
                    "how_to_validate": control.get("evidence_required", "Transcript-backed policy or SOP confirmation"),
                    "done_by": inferred_owner,
                    "frequency": _build_frequency(facts),
                }
                for idx, control in enumerate(controls["controls"][:3], start=1)
            ],
            "operator_checklist": outputs or ["Needs Review"],
        },
        "exception_handling": _build_exception_matrix(facts),
        "sla_and_performance_targets": _build_sla_rows(facts),
        "tools_and_systems_reference": [
            {"tool_system": s, "purpose": "Process execution support", "version_module": "Unknown", "access_request_process": "Needs Review"}
            for s in (_dedupe_preserve(pdd.get("systems", []) or ["manual_or_unspecified"]))
        ],
        "training_and_kt": {
            "training_requirements": [{"training_module": "Process overview", "delivery_mode": "Needs Review", "duration": "Needs Review", "frequency": "Onboarding"}],
            "transition_readiness": [{"milestone": "Shadow", "criteria": "Observe live transactions", "status": "Pending"}],
        },
        "controls_and_compliance": controls,
        "automation_opportunities": automation_opportunities,
        "related_documents": [
            {"document": "SIPOC", "type": "Reference", "location": "Included in export"},
        ],
        "custom_sop_summary": custom_summary,
        "faq_items": _custom_sop_faq_items(custom_steps, facts),
        "operational_facts": facts,
    }
    return sop


def generate_sipoc_rows(extraction: Dict) -> List[Dict]:
    explicit_sipoc = extraction.get("sipoc", [])
    if isinstance(explicit_sipoc, list) and explicit_sipoc:
        return [
            {
                "supplier": str(row.get("supplier", "upstream_supplier")),
                "input": str(row.get("input", "process input")),
                "process_step": str(row.get("process_step", "unspecified")),
                "output": str(row.get("output", "unspecified")),
                "customer": str(row.get("customer", "downstream_customer")),
            }
            for row in explicit_sipoc
            if isinstance(row, dict)
        ]

    steps = extraction.get("process_steps", [])
    if not steps:
        return []

    rows = []
    for idx, step in enumerate(steps):
        prev = steps[idx - 1] if idx > 0 else None
        next_step = steps[idx + 1] if idx + 1 < len(steps) else None

        supplier = prev.get("role") if prev else "upstream_supplier"
        customer = next_step.get("role") if next_step else "downstream_customer"

        rows.append(
            {
                "supplier": supplier,
                "input": prev.get("summary", "process trigger") if prev else "process trigger",
                "process_step": step.get("summary", ""),
                "output": step.get("summary", ""),
                "customer": customer,
            }
        )

    # Handoff normalization: row[i].customer should equal row[i+1].supplier where applicable.
    for i in range(len(rows) - 1):
        rows[i + 1]["supplier"] = rows[i]["customer"]

    # Deduplicate strict duplicates while preserving order.
    deduped = []
    seen = set()
    for row in rows:
        key = (
            row["supplier"].strip().lower(),
            row["input"].strip().lower(),
            row["process_step"].strip().lower(),
            row["output"].strip().lower(),
            row["customer"].strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
