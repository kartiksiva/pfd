from typing import Dict, List


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
