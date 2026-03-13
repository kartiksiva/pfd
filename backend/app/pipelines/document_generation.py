from typing import Dict, List, Optional


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


def generate_pdd_document(extraction: Dict) -> Dict:
    steps = extraction.get("process_steps", [])
    roles = extraction.get("roles", [])
    systems = extraction.get("systems", [])

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
        "business_rules": extraction.get("business_rules", []),
        "exceptions": extraction.get("exceptions", []),
        "outputs": extraction.get("outputs", []),
        "metrics": extraction.get("metrics", []),
        "risks": extraction.get("risks", []),
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
        max_ts = frames[-1]["timestamp_seconds"]
        for idx in range(len(step_rows)):
            ratio = idx / max(len(step_rows) - 1, 1)
            indexed_targets.append(max_ts * ratio)

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
    pdd["steps"] = mapped_steps

    if document_type != "sop":
        return pdd

    scope_text = str(pdd.get("scope", "Current-state process only."))
    sop = {
        "document_control": {
            "sop_id": "SOP-OPS-001-" + str(pdd.get("purpose", "") or "YYYY")[:4],
            "sop_title": mapped_steps[0].get("title", "Standard Operating Procedure") if mapped_steps else "Standard Operating Procedure",
            "process_owner": "Needs Review",
            "department": "Needs Review",
            "effective_date": "Needs Review",
            "review_date": "Needs Review",
            "version": "1.0",
            "classification": "Internal",
            "source_reference": "Generated from uploaded transcript/audio/video evidence",
        },
        "revision_history": [{"version": "1.0", "date": "Needs Review", "author": "PFCD Agent", "change_summary": "Initial Draft", "approved_by": "Needs Review"}],
        "purpose": pdd.get("purpose", "Needs Review"),
        "scope": {
            "in_scope": [scope_text] if scope_text else ["Needs Review"],
            "out_of_scope": ["Future-state redesign and optimization."],
            "regions_entities": [{"region_entity": "Needs Review", "applicable": "Needs Review", "notes": "Needs Review"}],
        },
        "roles_and_responsibilities": [
            {"role": role, "responsibility": "Execute assigned steps", "team_location": "Needs Review"}
            for role in (pdd.get("roles", []) or ["Operator"])
        ],
        "definitions": [
            {"term": "SOP", "definition": "Standard Operating Procedure"},
            {"term": "SLA", "definition": "Service Level Agreement"},
        ],
        "prerequisites_and_inputs": {
            "system_access_required": [{"system": s, "access_level": "Needs Review", "url_path": "Needs Review"} for s in (pdd.get("systems", []) or ["manual_or_unspecified"])],
            "input_documents_data": [{"input": (pdd.get("triggers", []) or ["process trigger"])[0], "source": "Source evidence", "format": "Needs Review", "frequency": "Needs Review"}],
            "knowledge_skills_required": ["Needs Review"],
        },
        "process_overview": {
            "flow_summary": " -> ".join([step.get("title", f"Step {idx+1}") for idx, step in enumerate(mapped_steps[:8])]) or "Needs Review",
            "metrics_at_glance": [{"metric": "SLA / TAT", "target": "Needs Review"}],
        },
        "steps": mapped_steps,
        "quality_checks": {
            "checks": [{"check_id": "QC-01", "what_to_validate": "Output correctness", "how_to_validate": "Review against expected output", "done_by": "Needs Review", "frequency": "Needs Review"}],
            "operator_checklist": ["Output saved to correct system", "Case/ticket updated with completion status"],
        },
        "exception_handling": {
            "exception_matrix": [
                {
                    "exception_id": f"EXC-{idx+1:02d}",
                    "scenario": exc,
                    "trigger_symptom": "Observed during process execution",
                    "action_to_take": "Investigate, retry if safe, and escalate if persistent",
                    "escalation_path": "Operator -> Team Lead",
                }
                for idx, exc in enumerate(pdd.get("exceptions", []) or ["Needs Review"])
            ],
            "escalation_matrix": [{"level": "L1", "trigger_condition": "Operator cannot resolve", "contact": "Team Lead", "response_time": "30 min"}],
        },
        "sla_and_performance_targets": [
            {"kpi": "Accuracy Rate", "definition": "Completed steps without error", "target": "Needs Review", "measurement_method": "QC review"},
            {"kpi": "Turnaround Time", "definition": "Time from trigger to completion", "target": "Needs Review", "measurement_method": "System timestamps"},
        ],
        "tools_and_systems_reference": [
            {"tool_system": s, "purpose": "Process execution support", "version_module": "Unknown", "access_request_process": "Needs Review"}
            for s in (pdd.get("systems", []) or ["manual_or_unspecified"])
        ],
        "training_and_kt": {
            "training_requirements": [{"training_module": "Process overview", "delivery_mode": "Needs Review", "duration": "Needs Review", "frequency": "Onboarding"}],
            "transition_readiness": [{"milestone": "Shadow", "criteria": "Observe live transactions", "status": "Pending"}],
        },
        "controls_and_compliance": {
            "controls": [{"control": "Process checklist completion", "type": "Detective", "description": "Confirm all critical steps complete", "evidence_required": "Checklist"}],
            "policies": ["Needs Review"],
        },
        "related_documents": [
            {"document": "SIPOC", "type": "Reference", "location": "Included in export"},
        ],
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
