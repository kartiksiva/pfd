import os
import re
from datetime import date
from pathlib import Path
from typing import Dict, List


def _as_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _split_exceptions(exceptions: list[str]) -> tuple[list[str], list[str]]:
    technical_markers = ("system", "down", "outage", "error", "timeout", "network", "api", "technical")
    business, technical = [], []
    for exc in exceptions:
        target = technical if any(marker in exc.lower() for marker in technical_markers) else business
        target.append(exc)
    return business, technical


def _read_template_text() -> str:
    # Precedence: explicit env var, then common local/container paths.
    candidates = []
    configured = os.getenv("PDD_TEMPLATE_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.extend(
        [
            Path("/STANDARD_PDD_TEMPLATE.md"),
            Path("../STANDARD_PDD_TEMPLATE.md"),
            Path("STANDARD_PDD_TEMPLATE.md"),
        ]
    )

    for path in candidates:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")

    # Minimal fallback keeps generation functional even if template is missing.
    return (
        "# [Process Name] - Process Definition Document (PDD)\n\n"
        "## 1. Document Control\n"
        "| Version | Date | Author | Description |\n"
        "| :--- | :--- | :--- | :--- |\n"
        "| 1.0 | 2026-03-05 | [Author Name] | Initial Draft (As-Is Process) |\n\n"
        "## 2. Process Overview\n"
        "*   **Process Name:** [e.g., Invoice Validation]\n"
        "*   **Objective:** [Short description of why the process exists]\n"
        "*   **Frequency:** [e.g., Daily / On-demand]\n"
        "*   **Estimated Volume:** [e.g., 50 cases/day]\n"
        "*   **Manual Effort:** [e.g., 15 mins per case]\n\n"
        "## 3. Scope\n"
        "### 3.1 In-Scope\n*   [e.g., Scope item]\n\n"
        "### 3.2 Out-of-Scope\n*   [e.g., Out-of-scope item]\n\n"
        "## 4. Prerequisites & Systems\n"
        "### 4.1 Prerequisites\n*   [e.g., prerequisite]\n\n"
        "### 4.2 Application Inventory\n"
        "| Application | Version | Access Method |\n"
        "| :--- | :--- | :--- |\n"
        "| Unspecified | Unknown | Unknown |\n\n"
        "---\n\n"
        "## 5. Detailed Process Steps (As-Is)\n"
        "| Step # | Action | Role | System | Input | Output |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n"
        "| 1.1 | Step details unavailable | Unspecified | Unspecified | Unspecified | Unspecified |\n\n"
        "## 6. Business Rules & Logic\n*   No explicit rules identified.\n\n"
        "## 7. Exceptions Handling\n### 7.1 Business Exceptions\n*   None captured.\n\n### 7.2 Technical Exceptions\n*   None captured.\n\n"
        "## 8. Inputs & Outputs\n*   **Primary Input:** Unspecified\n*   **Primary Output:** Unspecified\n\n"
        "## 9. Metrics & Risks\n*   **Success Metric:** Not explicitly defined.\n*   **Risk:** No explicit risks identified.\n\n"
        "---\n**Document generated for Process Excellence / Automation Readiness.**\n"
    )


def _replace_between(text: str, start_heading: str, end_heading: str, replacement_block: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_heading)}\n)(.*?)(?=\n{re.escape(end_heading)})",
        flags=re.DOTALL,
    )
    return pattern.sub(rf"\1{replacement_block}\n", text, count=1)


def _section_bullets(items: list[str], fallback: str) -> str:
    if not items:
        return f"*   {fallback}"
    return "\n".join(f"*   {item}" for item in items)


def _step_screenshot_block(steps: list[dict]) -> str:
    if not steps:
        return "### Step Screenshots\n*   No step screenshots available."
    lines = ["### Step Screenshots"]
    for step in steps:
        step_no = step.get("step_no", "")
        label = step.get("title", "") or step.get("description", "") or f"Step {step_no}"
        timestamp = str(step.get("source_timestamp", "")).strip()
        screenshot = step.get("screenshot") if isinstance(step.get("screenshot"), dict) else {}
        screenshot_path = str(screenshot.get("path", "")).strip()
        reason = str(screenshot.get("reason", "")).strip()
        lines.append(f"#### Step {step_no} - {label}")
        if timestamp:
            lines.append(f"*   **Source Timestamp:** {timestamp}")
        if screenshot_path and Path(screenshot_path).exists():
            lines.append(f"![Step {step_no} Screenshot]({screenshot_path})")
            if reason:
                lines.append(f"*   **Frame Reason:** {reason}")
        else:
            lines.append("*   Screenshot: Not available")
    return "\n".join(lines)


def render_standard_pdd_markdown(pdd: Dict, sipoc: List[Dict]) -> str:
    template = _read_template_text()

    purpose = str(pdd.get("purpose", "")).strip() or "Document current process flow from submitted evidence."
    scope = str(pdd.get("scope", "")).strip() or "Current-state process only."
    triggers = _as_list(pdd.get("triggers"))
    preconditions = _as_list(pdd.get("preconditions"))
    steps = pdd.get("steps", []) if isinstance(pdd.get("steps"), list) else []
    systems = _as_list(pdd.get("systems"))
    business_rules = _as_list(pdd.get("business_rules"))
    exceptions = _as_list(pdd.get("exceptions"))
    outputs = _as_list(pdd.get("outputs"))
    metrics = _as_list(pdd.get("metrics"))
    risks = _as_list(pdd.get("risks"))
    business_exceptions, technical_exceptions = _split_exceptions(exceptions)

    process_name = (steps[0].get("title", "") if steps else "").strip() or "Analyzed Process"

    text = template
    text = re.sub(
        r"^# .* - Process Definition Document \(PDD\)$",
        f"# {process_name} - Process Definition Document (PDD)",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r"\| 1\.0 \| .*? \| \[Author Name\] \| Initial Draft \(As-Is Process\) \|",
        f"| 1.0 | {date.today().isoformat()} | PFCD Agent | Initial Draft (As-Is Process) |",
        text,
        count=1,
    )

    section2 = "\n".join(
        [
            f"*   **Process Name:** {process_name}",
            f"*   **Objective:** {purpose}",
            f"*   **Frequency:** {triggers[0] if triggers else 'TBD'}",
            "*   **Estimated Volume:** TBD",
            "*   **Manual Effort:** TBD",
        ]
    )
    text = _replace_between(text, "## 2. Process Overview", "## 3. Scope", section2)

    section3 = "\n".join(
        [
            "### 3.1 In-Scope",
            _section_bullets([scope], "Scope not explicitly stated."),
            "",
            "### 3.2 Out-of-Scope",
            _section_bullets(["Future-state redesign and optimization."], "Not specified."),
        ]
    )
    text = _replace_between(text, "## 3. Scope", "## 4. Prerequisites & Systems", section3)

    app_rows = (
        "\n".join(f"| {app} | Unknown | As observed in evidence |" for app in systems)
        if systems
        else "| Unspecified | Unknown | Unknown |"
    )
    section4 = "\n".join(
        [
            "### 4.1 Prerequisites",
            _section_bullets(preconditions, "None explicitly stated in source evidence."),
            "",
            "### 4.2 Application Inventory",
            "| Application | Version | Access Method |",
            "| :--- | :--- | :--- |",
            app_rows,
        ]
    )
    text = _replace_between(text, "## 4. Prerequisites & Systems", "---", section4)

    step_rows = []
    if steps:
        for row in steps:
            step_rows.append(
                "| {step_no} | {action} | {role} | {system} | {input} | {output} |".format(
                    step_no=row.get("step_no", ""),
                    action=row.get("description", "") or row.get("title", ""),
                    role=row.get("actor", ""),
                    system=row.get("system", ""),
                    input=row.get("input", ""),
                    output=row.get("output", ""),
                )
            )
    else:
        step_rows.append("| 1.1 | Step details unavailable | Unspecified | Unspecified | Unspecified | Unspecified |")

    section5 = "\n".join(
        [
            "*This is the core of the document. Use a table for structured steps and nested lists for complex logic.*",
            "",
            "| Step # | Action | Role | System | Input | Output |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
            *step_rows,
            "",
            "### Step Details",
            "1.  Follow the sequence listed in the table above.",
            "2.  Apply business rules and exception handling where applicable.",
            "",
            _step_screenshot_block(steps),
        ]
    )
    text = _replace_between(text, "## 5. Detailed Process Steps (As-Is)", "## 6. Business Rules & Logic", section5)

    rules_lines = "*Define the 'brains' of the process.*\n"
    if business_rules:
        rules_lines += "\n".join(f"*   **Rule {idx}:** {rule}" for idx, rule in enumerate(business_rules, start=1))
    else:
        rules_lines += "*   No explicit business rules identified from source evidence."
    text = _replace_between(text, "## 6. Business Rules & Logic", "## 7. Exceptions Handling", rules_lines)

    business_lines = (
        "\n".join(f"*   **Scenario:** {exc}\n*   **Action:** Requires business review and follow-up." for exc in business_exceptions)
        if business_exceptions
        else "*   None captured."
    )
    technical_lines = (
        "\n".join(
            f"*   **Scenario:** {exc}\n*   **Action:** Retry, log, and escalate to technical owner if persistent."
            for exc in technical_exceptions
        )
        if technical_exceptions
        else "*   None captured."
    )
    section7 = "\n".join(
        [
            "### 7.1 Business Exceptions",
            business_lines,
            "",
            "### 7.2 Technical Exceptions",
            technical_lines,
        ]
    )
    text = _replace_between(text, "## 7. Exceptions Handling", "## 8. Inputs & Outputs", section7)

    primary_input = sipoc[0].get("input", "") if sipoc else "Unspecified"
    primary_output = outputs[0] if outputs else (sipoc[-1].get("output", "") if sipoc else "Unspecified")
    section8 = "\n".join(
        [
            f"*   **Primary Input:** {primary_input}",
            f"*   **Primary Output:** {primary_output}",
        ]
    )
    text = _replace_between(text, "## 8. Inputs & Outputs", "## 9. Metrics & Risks", section8)

    metric_lines = (
        "\n".join(f"*   **Success Metric:** {metric}" for metric in metrics)
        if metrics
        else "*   **Success Metric:** Not explicitly defined."
    )
    risk_lines = (
        "\n".join(f"*   **Risk:** {risk}\n*   **Mitigation:** Define owner, threshold, and contingency action." for risk in risks)
        if risks
        else "*   **Risk:** No explicit risks identified."
    )
    section9 = "\n".join([metric_lines, risk_lines])
    text = _replace_between(text, "## 9. Metrics & Risks", "---", section9)

    sipoc_lines = [
        "## 10. SIPOC",
        "| Supplier | Input | Process | Output | Customer |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    if sipoc:
        for row in sipoc:
            sipoc_lines.append(
                "| {supplier} | {input} | {process} | {output} | {customer} |".format(
                    supplier=str(row.get("supplier", "")),
                    input=str(row.get("input", "")),
                    process=str(row.get("process_step", "")),
                    output=str(row.get("output", "")),
                    customer=str(row.get("customer", "")),
                )
            )
    else:
        sipoc_lines.append("| upstream_supplier | process input | unspecified | unspecified | downstream_customer |")

    text = text.replace(
        "\n---\n**Document generated for Process Excellence / Automation Readiness.**",
        "\n\n" + "\n".join(sipoc_lines) + "\n\n---\n**Document generated for Process Excellence / Automation Readiness.**",
    )
    return text.strip() + "\n"


def render_sop_markdown(document: Dict, sipoc: List[Dict]) -> str:
    steps = document.get("steps", []) if isinstance(document.get("steps"), list) else []
    doc_control = document.get("document_control", {}) if isinstance(document.get("document_control"), dict) else {}
    revision_history = document.get("revision_history", []) if isinstance(document.get("revision_history"), list) else []
    scope = document.get("scope", {}) if isinstance(document.get("scope"), dict) else {}
    prerequisites = (
        document.get("prerequisites_and_inputs", {})
        if isinstance(document.get("prerequisites_and_inputs"), dict)
        else {}
    )
    overview = document.get("process_overview", {}) if isinstance(document.get("process_overview"), dict) else {}
    quality = document.get("quality_checks", {}) if isinstance(document.get("quality_checks"), dict) else {}
    exceptions = document.get("exception_handling", {}) if isinstance(document.get("exception_handling"), dict) else {}
    controls = document.get("controls_and_compliance", {}) if isinstance(document.get("controls_and_compliance"), dict) else {}
    training = document.get("training_and_kt", {}) if isinstance(document.get("training_and_kt"), dict) else {}
    related_docs = document.get("related_documents", []) if isinstance(document.get("related_documents"), list) else []

    lines: list[str] = []
    lines.append("# Standard Operating Procedure (SOP)")
    lines.append("")
    lines.append("## Document Control")
    lines.append("| Field | Details |")
    lines.append("|---|---|")
    for key in ("sop_id", "sop_title", "process_owner", "department", "effective_date", "review_date", "version", "classification", "source_reference"):
        pretty = key.replace("_", " ").title()
        lines.append(f"| **{pretty}** | {doc_control.get(key, 'Needs Review')} |")
    lines.append("")
    lines.append("### Revision History")
    lines.append("| Version | Date | Author | Change Summary | Approved By |")
    lines.append("|---|---|---|---|---|")
    if revision_history:
        for row in revision_history:
            lines.append(
                f"| {row.get('version','')} | {row.get('date','')} | {row.get('author','')} | {row.get('change_summary','')} | {row.get('approved_by','')} |"
            )
    else:
        lines.append("| 1.0 | Needs Review | PFCD Agent | Initial Draft | Needs Review |")
    lines.append("")
    lines.append("## 1. Purpose")
    lines.append(str(document.get("purpose", "Needs Review")))
    lines.append("")
    lines.append("## 2. Scope")
    lines.append("### 2.1 In-Scope")
    for item in scope.get("in_scope", []) if isinstance(scope.get("in_scope"), list) else ["Needs Review"]:
        lines.append(f"- {item}")
    lines.append("### 2.2 Out-of-Scope")
    for item in scope.get("out_of_scope", []) if isinstance(scope.get("out_of_scope"), list) else ["Needs Review"]:
        lines.append(f"- {item}")
    lines.append("### 2.3 Applicable Regions / Entities")
    lines.append("| Region / Entity | Applicable? | Notes |")
    lines.append("|---|---|---|")
    regions = scope.get("regions_entities", [])
    if isinstance(regions, list) and regions:
        for row in regions:
            lines.append(f"| {row.get('region_entity','')} | {row.get('applicable','')} | {row.get('notes','')} |")
    else:
        lines.append("| Needs Review | Needs Review | Needs Review |")
    lines.append("")
    lines.append("## 3. Roles & Responsibilities")
    lines.append("| Role | Responsibility | Team / Location |")
    lines.append("|---|---|---|")
    roles = document.get("roles_and_responsibilities", [])
    if isinstance(roles, list) and roles:
        for row in roles:
            lines.append(f"| {row.get('role','')} | {row.get('responsibility','')} | {row.get('team_location','')} |")
    else:
        lines.append("| Operator | Execute process steps | Needs Review |")
    lines.append("")
    lines.append("## 4. Definitions & Abbreviations")
    lines.append("| Term / Acronym | Definition |")
    lines.append("|---|---|")
    definitions = document.get("definitions", [])
    if isinstance(definitions, list) and definitions:
        for row in definitions:
            lines.append(f"| {row.get('term','')} | {row.get('definition','')} |")
    else:
        lines.append("| SOP | Standard Operating Procedure |")
    lines.append("")
    lines.append("## 5. Prerequisites & Inputs")
    lines.append("### 5.1 System Access Required")
    lines.append("| System / Application | Access Level | URL / Path |")
    lines.append("|---|---|---|")
    for row in prerequisites.get("system_access_required", []) or [{"system": "Needs Review", "access_level": "Needs Review", "url_path": "Needs Review"}]:
        lines.append(f"| {row.get('system','')} | {row.get('access_level','')} | {row.get('url_path','')} |")
    lines.append("### 5.2 Input Documents / Data")
    lines.append("| Input | Source | Format | Frequency |")
    lines.append("|---|---|---|---|")
    for row in prerequisites.get("input_documents_data", []) or [{"input": "Needs Review", "source": "Needs Review", "format": "Needs Review", "frequency": "Needs Review"}]:
        lines.append(f"| {row.get('input','')} | {row.get('source','')} | {row.get('format','')} | {row.get('frequency','')} |")
    lines.append("")
    lines.append("## 6. Process Overview")
    lines.append(str(overview.get("flow_summary", "Needs Review")))
    lines.append("")
    lines.append("## 7. Detailed Process Steps")
    for idx, step in enumerate(steps, start=1):
        lines.append(f"### STEP {idx} - {step.get('title', f'Step {idx}')}")
        lines.append(f"- **Performed By:** {step.get('actor', 'operator')}")
        lines.append(f"- **System Used:** {step.get('system', 'manual_or_unspecified')}")
        lines.append(f"- **Source Timestamp:** {step.get('source_timestamp', 'Needs Review')}")
        lines.append(f"- **Action:** {step.get('description', '')}")
        lines.append(f"- **Expected Result:** {step.get('output', '')}")
        screenshot = step.get("screenshot") if isinstance(step.get("screenshot"), dict) else {}
        screenshot_path = str(screenshot.get("path", "")).strip()
        if screenshot_path and Path(screenshot_path).exists():
            lines.append(f"![Step {idx} Screenshot]({screenshot_path})")
            lines.append(f"- **Frame Reason:** {screenshot.get('reason', 'process_event')}")
        else:
            lines.append("- Screenshot: Not available")
        lines.append("")
    lines.append("## 8. Quality Checks & Validation")
    lines.append("| Check # | What to Validate | How to Validate | Done By | Frequency |")
    lines.append("|---|---|---|---|---|")
    for row in quality.get("checks", []) or [{"check_id": "QC-01", "what_to_validate": "Needs Review", "how_to_validate": "Needs Review", "done_by": "Needs Review", "frequency": "Needs Review"}]:
        lines.append(f"| {row.get('check_id','')} | {row.get('what_to_validate','')} | {row.get('how_to_validate','')} | {row.get('done_by','')} | {row.get('frequency','')} |")
    lines.append("")
    lines.append("## 9. Exception Handling")
    lines.append("| Exception ID | Scenario | Trigger / Symptom | Action to Take | Escalation Path |")
    lines.append("|---|---|---|---|---|")
    for row in exceptions.get("exception_matrix", []) or [{"exception_id": "EXC-01", "scenario": "Needs Review", "trigger_symptom": "Needs Review", "action_to_take": "Needs Review", "escalation_path": "Needs Review"}]:
        lines.append(f"| {row.get('exception_id','')} | {row.get('scenario','')} | {row.get('trigger_symptom','')} | {row.get('action_to_take','')} | {row.get('escalation_path','')} |")
    lines.append("")
    lines.append("## 10. SLA & Performance Targets")
    lines.append("| KPI | Definition | Target | Measurement Method |")
    lines.append("|---|---|---|---|")
    for row in document.get("sla_and_performance_targets", []) or [{"kpi": "Accuracy Rate", "definition": "Needs Review", "target": "Needs Review", "measurement_method": "Needs Review"}]:
        lines.append(f"| {row.get('kpi','')} | {row.get('definition','')} | {row.get('target','')} | {row.get('measurement_method','')} |")
    lines.append("")
    lines.append("## 11. Tools & Systems Reference")
    lines.append("| Tool / System | Purpose in Process | Version / Module | Access Request Process |")
    lines.append("|---|---|---|---|")
    for row in document.get("tools_and_systems_reference", []) or [{"tool_system": "Needs Review", "purpose": "Needs Review", "version_module": "Needs Review", "access_request_process": "Needs Review"}]:
        lines.append(f"| {row.get('tool_system','')} | {row.get('purpose','')} | {row.get('version_module','')} | {row.get('access_request_process','')} |")
    lines.append("")
    lines.append("## 12. Training & Knowledge Transfer")
    lines.append("| Training Module | Delivery Mode | Duration | Frequency |")
    lines.append("|---|---|---|---|")
    for row in training.get("training_requirements", []) or [{"training_module": "Needs Review", "delivery_mode": "Needs Review", "duration": "Needs Review", "frequency": "Needs Review"}]:
        lines.append(f"| {row.get('training_module','')} | {row.get('delivery_mode','')} | {row.get('duration','')} | {row.get('frequency','')} |")
    lines.append("")
    lines.append("## 13. Controls & Compliance")
    lines.append("| Control | Type | Description | Evidence Required |")
    lines.append("|---|---|---|---|")
    for row in controls.get("controls", []) or [{"control": "Needs Review", "type": "Needs Review", "description": "Needs Review", "evidence_required": "Needs Review"}]:
        lines.append(f"| {row.get('control','')} | {row.get('type','')} | {row.get('description','')} | {row.get('evidence_required','')} |")
    lines.append("")
    lines.append("## 14. Related Documents")
    lines.append("| Document | Type | Location |")
    lines.append("|---|---|---|")
    for row in related_docs or [{"document": "SIPOC", "type": "Reference", "location": "Embedded in job export JSON"}]:
        lines.append(f"| {row.get('document','')} | {row.get('type','')} | {row.get('location','')} |")
    lines.append("")
    lines.append("## SIPOC")
    lines.append("| Supplier | Input | Process | Output | Customer |")
    lines.append("|---|---|---|---|---|")
    if sipoc:
        for row in sipoc:
            lines.append(
                f"| {row.get('supplier','')} | {row.get('input','')} | {row.get('process_step','')} | {row.get('output','')} | {row.get('customer','')} |"
            )
    else:
        lines.append("| upstream_supplier | process input | unspecified | unspecified | downstream_customer |")
    return "\n".join(lines).strip() + "\n"


def render_document_markdown(document: Dict, sipoc: List[Dict], document_type: str) -> str:
    if document_type == "sop":
        return render_sop_markdown(document=document, sipoc=sipoc)
    return render_standard_pdd_markdown(pdd=document, sipoc=sipoc)
