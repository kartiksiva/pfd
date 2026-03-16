import os
import re
from datetime import date
from pathlib import Path
from typing import Dict, List

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

STANDARD_PDD_TEMPLATE_FALLBACK = """# [Process Name] - Process Definition Document (PDD)

## 1. Document Control
| Version | Date | Author | Description |
| :--- | :--- | :--- | :--- |
| 1.0 | 2026-03-05 | [Author Name] | Initial Draft (As-Is Process) |

## 2. Process Overview
*   **Process Name:** [e.g., Invoice Validation]
*   **Objective:** [Short description of why the process exists]
*   **Frequency:** [e.g., Daily / On-demand]
*   **Estimated Volume:** [e.g., 50 cases/day]
*   **Manual Effort:** [e.g., 15 mins per case]

## 3. Scope
### 3.1 In-Scope
*   [e.g., Processing PDF invoices from the 'AP_Inbox']
*   [e.g., Data entry into SAP FICO module]

### 3.2 Out-of-Scope
*   [e.g., Physical paper invoices]
*   [e.g., Handling tax disputes (requires Human-in-the-Loop)]

## 4. Prerequisites & Systems
### 4.1 Prerequisites
*   [e.g., Access to Shared Drive]
*   [e.g., Active SAP User Profile]

### 4.2 Application Inventory
| Application | Version | Access Method |
| :--- | :--- | :--- |
| SAP S/4HANA | v2023 | Desktop Client |
| Microsoft Outlook | Office 365 | Web/Desktop |
| Internal Portal | v1.2 | Chrome/Edge |

---

## 5. Detailed Process Steps (As-Is)
*This is the core of the document. Use a table for structured steps and nested lists for complex logic.*

| Step # | Action | Role | System | Input | Output |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1.1 | Open Outlook and navigate to 'Invoices' folder. | Operator | Outlook | Email | Invoice PDF |
| 1.2 | Download the attachment to the 'Pending' directory. | Operator | File Explorer | PDF | File on Local Path |
| 1.3 | Open Internal Portal and upload the PDF for OCR. | Operator | Web Portal | File | Extracted Data |
| 1.4 | Compare Extracted Data with SAP Records. | Analyst | SAP | Data | Validation Result |

### Step 1.4 Details (Sub-steps)
1.  Log into **SAP** using credentials.
2.  Enter Transaction Code **FB60**.
3.  **If** Invoice Number exists:
    *   Proceed to Step 1.5.
4.  **Else** (Invoice missing):
    *   Route to "Business Exception - Missing PO".

---

## 6. Business Rules & Logic
*Define the 'brains' of the process.*
*   **Rule 1:** Only process invoices where the Total Amount is > $0.
*   **Rule 2:** Invoices from "Vendor X" must be routed to the Priority Queue.

## 7. Exceptions Handling
### 7.1 Business Exceptions
*   **Scenario:** Duplicate Invoice Number.
*   **Action:** Move to 'Duplicates' folder and notify requester via email.

### 7.2 Technical Exceptions
*   **Scenario:** SAP System Down.
*   **Action:** Wait 15 minutes and retry; if persistent, alert IT Support.

## 8. Inputs & Outputs
*   **Primary Input:** PDF Document via Email.
*   **Primary Output:** Verified Record in SAP; Confirmation Email.

## 9. Metrics & Risks
*   **Success Metric:** Accuracy Rate > 98%.
*   **Risk:** Poor OCR quality on handwritten invoices.
*   **Mitigation:** Human-in-the-loop review for confidence scores < 85%.

---
**Document generated for Process Excellence / Automation Readiness.**
"""

CUSTOM_SOP_TEMPLATE_FALLBACK = """# Standard Operating Procedure (SOP) Template
**SOP Format**

---

## <Process Name>

**Function:** <Function Name>
**Sub-Function:** <Sub-function Name>
**Document Version:** <vX.X>
**Document Status:** Draft / Final
**Effective Date:** <DD-MMM-YYYY>

---

## 1. Document Control

### 1.1 Key Stakeholders

| # | Name | Position / Designation | Email ID |
|---|------|------------------------|----------|
| 1 | <Name> | <Role> | <email@domain> |
| 2 | <Name> | <Role> | <email@domain> |
| 3 | <Name> | <Role> | <email@domain> |

---

### 1.2 Version History

| Version | Date | Status (Draft/Final) | Author | Reviewed By | Comments / Changes |
|---------|------|----------------------|--------|-------------|-------------------|
| 0.1 | <DD-MMM-YYYY> | Draft | <Name> | <Name> | Initial draft |
| 1.0 | <DD-MMM-YYYY> | Final | <Name> | <Name> | Approved version |

---

## Index

1. Document Control
2. Introduction
3. Process Steps
4. Process Exceptions
5. Process Controls
6. Approval Matrix
7. Appendix

---

## 2. Introduction

### 2.1 Process Overview
<Brief description of the process>

---

### 2.2 Process Objective
- <Objective 1>
- <Objective 2>
- <Objective 3>

---

### 2.3 Frequency
<Daily / Weekly / Monthly / Ad-hoc>

---

### 2.4 SLA
- <Turnaround time / SLA details>

---

### 2.5 RACI

| Task / Stakeholders | Role 1 | Role 2 | Role 3 |
|---------------------|--------|--------|--------|
| <Task 1> | R | I | A |
| <Task 2> | I | R | A |
| <Task 3> | C | R | I |

---

### 2.6 SIPOC

**Supplier**
- <Supplier>

**Input**
- <Inputs>

**Process**
- <High-level steps>

**Output**
- <Outputs>

**Customer**
- <Customers>

---

### 2.7 High Level Process Flow
<Optional process flow description or diagram reference>

---

## 3. Process Steps

### Step 1: <Step Name>
- Description
- Tools / Systems
- Inputs

### Step 2: <Step Name>
- Description
- Validation / Checks
- Outputs

*(Add more steps as required)*

---

## 4. Process Exceptions

| Exception Scenario | Description | Action Required | Owner |
|--------------------|-------------|-----------------|-------|
| <Exception 1> | <Details> | <Resolution> | <Role> |
| <Exception 2> | <Details> | <Resolution> | <Role> |

---

## 5. Process Controls

| Control # | Process Step | Control Description | Manual / System | Preventive / Detective |
|-----------|-------------|---------------------|-----------------|------------------------|
| C1 | <Step Name> | <Control Description> | Manual | Preventive |
| C2 | <Step Name> | <Control Description> | System | Detective |
| C3 | <Step Name> | <Control Description> | Manual | Detective |

---

## 6. Approval Matrix

| Role | Responsibility |
|------|----------------|
| <Role 1> | Review |
| <Role 2> | Approval |
| <Role 3> | Final Sign-off |

---

## 7. Appendix

### Frequently Asked Questions (FAQs)

| # | Topic | Top Tips |
|---|-------|----------|
| 1 | <FAQ Topic> | <Guidance> |
| 2 | <FAQ Topic> | <Guidance> |
| 3 | <FAQ Topic> | <Guidance> |

---
"""


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
    # Precedence: explicit env var, bundled template path.
    candidates = []
    configured = os.getenv("PDD_TEMPLATE_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.append(TEMPLATES_DIR / "STANDARD_PDD_TEMPLATE.md")

    for path in candidates:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")

    return STANDARD_PDD_TEMPLATE_FALLBACK


def _read_custom_sop_template_text() -> str:
    candidates = []
    configured = os.getenv("CUSTOM_SOP_TEMPLATE_PATH", "").strip()
    if configured:
        candidates.append(Path(configured))
    candidates.append(TEMPLATES_DIR / "Custom_SOP_Template.md")

    for path in candidates:
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")

    return CUSTOM_SOP_TEMPLATE_FALLBACK


def _replace_between(text: str, start_heading: str, end_heading: str, replacement_block: str) -> str:
    pattern = re.compile(
        rf"({re.escape(start_heading)}\n)(.*?)(?=\n{re.escape(end_heading)})",
        flags=re.DOTALL,
    )
    return pattern.sub(rf"\1{replacement_block}\n", text, count=1)


def _collapse_duplicate_headings(text: str) -> str:
    return re.sub(r"^(#{2,3}\s+[^\n]+)\n\1\n+", r"\1\n", text, flags=re.MULTILINE)


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


def render_custom_sop_markdown(document: Dict, sipoc: List[Dict]) -> str:
    template = _read_custom_sop_template_text()
    steps = document.get("steps", []) if isinstance(document.get("steps"), list) else []
    doc_control = document.get("document_control", {}) if isinstance(document.get("document_control"), dict) else {}
    scope = document.get("scope", {}) if isinstance(document.get("scope"), dict) else {}
    exceptions = document.get("exception_handling", {}) if isinstance(document.get("exception_handling"), dict) else {}
    controls = document.get("controls_and_compliance", {}) if isinstance(document.get("controls_and_compliance"), dict) else {}
    training = document.get("training_and_kt", {}) if isinstance(document.get("training_and_kt"), dict) else {}
    overview = document.get("process_overview", {}) if isinstance(document.get("process_overview"), dict) else {}
    prerequisites = (
        document.get("prerequisites_and_inputs", {})
        if isinstance(document.get("prerequisites_and_inputs"), dict)
        else {}
    )
    tools = document.get("tools_and_systems_reference", []) if isinstance(document.get("tools_and_systems_reference"), list) else []
    roles = document.get("roles_and_responsibilities", []) if isinstance(document.get("roles_and_responsibilities"), list) else []
    revision_history = document.get("revision_history", []) if isinstance(document.get("revision_history"), list) else []
    sla_rows = document.get("sla_and_performance_targets", []) if isinstance(document.get("sla_and_performance_targets"), list) else []
    custom_summary = document.get("custom_sop_summary", {}) if isinstance(document.get("custom_sop_summary"), dict) else {}
    faq_items = document.get("faq_items", []) if isinstance(document.get("faq_items"), list) else []

    process_name = (
        str(doc_control.get("sop_title", "")).strip()
        or (str(steps[0].get("title", "")).strip() if steps else "")
        or "Standard Operating Procedure"
    )
    process_owner = str(doc_control.get("process_owner", "")).strip()
    if not process_owner or process_owner.lower() == "needs review":
        process_owner = (
            str(roles[0].get("role", "")).strip()
            if roles and isinstance(roles[0], dict)
            else (str(steps[0].get("actor", "")).strip() if steps else "")
        ) or "Needs Review"
    function_name = str(doc_control.get("department", "")).strip()
    if not function_name or function_name.lower() == "needs review":
        function_name = "Needs Review"
    effective_date_value = str(doc_control.get("effective_date", "")).strip()
    effective_date = effective_date_value if effective_date_value and effective_date_value.lower() != "needs review" else date.today().strftime("%d-%b-%Y")
    document_status = str(doc_control.get("status", "")).strip() or "Draft"
    frequency = "Needs Review"
    input_docs = prerequisites.get("input_documents_data", []) if isinstance(prerequisites, dict) else []
    if isinstance(input_docs, list) and input_docs:
        frequency = str(input_docs[0].get("frequency", "")).strip() or "Needs Review"
    sla_text = "Needs Review"
    if sla_rows:
        formatted = [f"{row.get('kpi', 'KPI')}: {row.get('target', 'Needs Review')}" for row in sla_rows[:2]]
        sla_text = "; ".join(formatted)

    suppliers = ", ".join(custom_summary.get("suppliers", [])) or ", ".join(sorted({str(row.get("supplier", "")).strip() for row in sipoc if str(row.get("supplier", "")).strip()})) or "Needs Review"
    inputs = ", ".join(custom_summary.get("inputs", [])) or ", ".join(sorted({str(row.get("input", "")).strip() for row in sipoc if str(row.get("input", "")).strip()})) or "Needs Review"
    processes = ", ".join([str(step.get("title", "")).strip() for step in steps if str(step.get("title", "")).strip()][:5]) or "Needs Review"
    outputs = ", ".join(custom_summary.get("outputs", [])) or ", ".join(sorted({str(row.get("output", "")).strip() for row in sipoc if str(row.get("output", "")).strip()})) or "Needs Review"
    customers = ", ".join(custom_summary.get("customers", [])) or ", ".join(sorted({str(row.get("customer", "")).strip() for row in sipoc if str(row.get("customer", "")).strip()})) or "Needs Review"

    primary_role = roles[0] if roles else {}
    secondary_role = roles[1] if len(roles) > 1 else {}
    tertiary_role = roles[2] if len(roles) > 2 else {}
    primary_exc = (exceptions.get("exception_matrix", []) or [{}])[0] if isinstance(exceptions, dict) else {}
    secondary_exc = (exceptions.get("exception_matrix", []) or [{}, {}])[1] if isinstance(exceptions, dict) and len(exceptions.get("exception_matrix", [])) > 1 else {}
    primary_control = (controls.get("controls", []) or [{}])[0] if isinstance(controls, dict) else {}
    secondary_control = (controls.get("controls", []) or [{}, {}])[1] if isinstance(controls, dict) and len(controls.get("controls", [])) > 1 else {}
    tertiary_control = (controls.get("controls", []) or [{}, {}, {}])[2] if isinstance(controls, dict) and len(controls.get("controls", [])) > 2 else {}
    training_rows = training.get("training_requirements", []) if isinstance(training, dict) else []

    role_labels = [
        str(primary_role.get("role", "Needs Review")),
        str(secondary_role.get("role", "Needs Review")),
        str(tertiary_role.get("role", "Needs Review")),
    ]
    owner_default = str(doc_control.get("process_owner", "Needs Review"))

    replacements = {
        "<Process Name>": process_name,
        "<Function Name>": function_name,
        "<Sub-function Name>": process_owner,
        "<vX.X>": str(doc_control.get("version", "1.0")),
        "<DD-MMM-YYYY>": effective_date,
        "<Brief description of the process>": str(overview.get("flow_summary", document.get("purpose", "Needs Review"))),
        "<Objective 1>": str(document.get("purpose", "Needs Review")),
        "<Objective 2>": str((scope.get("in_scope", ["Needs Review"])[0] if isinstance(scope.get("in_scope", []), list) and scope.get("in_scope") else "Needs Review")),
        "<Objective 3>": "Ensure consistent execution with controls and exception handling.",
        "<Daily / Weekly / Monthly / Ad-hoc>": frequency,
        "<Turnaround time / SLA details>": sla_text,
        "<Supplier>": suppliers,
        "<Inputs>": inputs,
        "<High-level steps>": processes,
        "<Outputs>": outputs,
        "<Customers>": customers,
        "<Optional process flow description or diagram reference>": str(overview.get("flow_summary", "Needs Review")),
        "<Step Name>": str(steps[0].get("title", "Process Step")) if steps else "Process Step",
        "<Exception 1>": str(primary_exc.get("scenario", "Needs Review")),
        "<Details>": str(primary_exc.get("trigger_symptom", "Needs Review")),
        "<Resolution>": str(primary_exc.get("action_to_take", "Needs Review")),
        "<Role>": str(primary_exc.get("escalation_path", "Needs Review")),
        "<Exception 2>": str(secondary_exc.get("scenario", "Needs Review")),
        "<Control Description>": str(primary_control.get("description", "Needs Review")),
        "<Role 1>": str(primary_role.get("role", "Needs Review")),
        "<Role 2>": str(secondary_role.get("role", "Needs Review")),
        "<Role 3>": str(tertiary_role.get("role", "Needs Review")),
        "<FAQ Topic>": str(training_rows[0].get("training_module", "Needs Review")) if training_rows else "Needs Review",
        "<Guidance>": str(training_rows[0].get("delivery_mode", "Needs Review")) if training_rows else "Needs Review",
        "<Task 1>": str(steps[0].get("title", "Task 1")) if steps else "Task 1",
        "<Task 2>": str(steps[1].get("title", "Task 2")) if len(steps) > 1 else "Task 2",
        "<Task 3>": str(steps[2].get("title", "Task 3")) if len(steps) > 2 else "Task 3",
        "<Name>": owner_default,
        "<email@domain>": "Needs Review",
        "<Control #>": "C1",
    }
    replacements.update(
        {
            "C1 | <Step Name> | <Control Description> | Manual | Preventive": (
                f"C1 | {str(steps[0].get('title', 'Process Step')) if steps else 'Process Step'} | "
                f"{str(primary_control.get('description', 'Needs Review'))} | Manual | Preventive"
            ),
            "C2 | <Step Name> | <Control Description> | System | Detective": (
                f"C2 | {str(steps[1].get('title', 'Process Step')) if len(steps) > 1 else 'Process Step'} | "
                f"{str(secondary_control.get('description', 'Needs Review'))} | System | Detective"
            ),
            "C3 | <Step Name> | <Control Description> | Manual | Detective": (
                f"C3 | {str(steps[2].get('title', 'Process Step')) if len(steps) > 2 else 'Process Step'} | "
                f"{str(tertiary_control.get('description', 'Needs Review'))} | Manual | Detective"
            ),
        }
    )

    rendered = template
    # Custom SOP output should be production-ready, not template-labeled.
    rendered = rendered.replace("# Standard Operating Procedure (SOP) Template", "# Standard Operating Procedure (SOP)")
    rendered = rendered.replace("**SOP Format**", "")
    rendered = rendered.replace("Draft / Final", document_status)
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, str(value))

    stakeholders_rows = [
        f"| {idx} | {row.get('role', owner_default)} | Needs Review | Needs Review |"
        for idx, row in enumerate(roles[:3], start=1)
    ] or [
        f"| 1 | {owner_default} | Needs Review | Needs Review |",
        "| 2 | Needs Review | Needs Review | Needs Review |",
        "| 3 | Needs Review | Needs Review | Needs Review |",
    ]
    stakeholders_block = "\n".join(
        [
            "| # | Name | Position / Designation | Email ID |",
            "|---|------|------------------------|----------|",
            *stakeholders_rows,
        ]
    )
    rendered = _replace_between(rendered, "### 1.1 Key Stakeholders", "---", stakeholders_block)

    version_rows = [
        "| {version} | {date} | {status} | {author} | {approved_by} | {change_summary} |".format(
            version=row.get("version", "1.0"),
            date=row.get("date", effective_date),
            status=row.get("status", "Draft"),
            author=row.get("author", "PFCD Agent"),
            approved_by=row.get("approved_by", "Needs Review"),
            change_summary=row.get("change_summary", "Update"),
        )
        for row in revision_history[:3]
    ] or [
        f"| 1.0 | {effective_date} | {document_status} | PFCD Agent | Needs Review | Initial draft |"
    ]
    version_block = "\n".join(
        [
            "| Version | Date | Status (Draft/Final) | Author | Reviewed By | Comments / Changes |",
            "|---------|------|----------------------|--------|-------------|-------------------|",
            *version_rows,
        ]
    )
    rendered = _replace_between(rendered, "### 1.2 Version History", "---", version_block)

    def _match_role(step_actor: str, role_label: str) -> bool:
        actor = str(step_actor or "").strip().lower()
        role = str(role_label or "").strip().lower()
        if not actor or not role or "needs review" in {actor, role}:
            return False
        if actor == role:
            return True
        actor_tokens = set(re.split(r"[^a-z0-9]+", actor))
        role_tokens = set(re.split(r"[^a-z0-9]+", role))
        actor_tokens.discard("")
        role_tokens.discard("")
        if actor in {"operator", "analyst", "user"} and actor in role_tokens:
            return True
        if actor_tokens and role_tokens and actor_tokens.issubset(role_tokens):
            return True
        return False

    raci_rows = []
    for idx in range(3):
        task = str(steps[idx].get("title", f"Task {idx + 1}")) if idx < len(steps) else f"Task {idx + 1}"
        actor = str(steps[idx].get("actor", "")) if idx < len(steps) else ""
        values = []
        for role_label in role_labels:
            values.append("R" if _match_role(actor, role_label) else "Needs Review")
        raci_rows.append(f"| {task} | {values[0]} | {values[1]} | {values[2]} |")
    raci_block = "\n".join(
        [
            "| Task / Stakeholders | Role 1 | Role 2 | Role 3 |",
            "|---------------------|--------|--------|--------|",
            *raci_rows,
        ]
    )
    rendered = _replace_between(rendered, "### 2.5 RACI", "---", raci_block)
    rendered = rendered.replace("Role 1", role_labels[0])
    rendered = rendered.replace("Role 2", role_labels[1])
    rendered = rendered.replace("Role 3", role_labels[2])

    process_steps_lines = []
    if steps:
        for idx, step in enumerate(steps, start=1):
            screenshot = step.get("screenshot") if isinstance(step.get("screenshot"), dict) else {}
            screenshot_path = str(screenshot.get("path", "")).strip()
            process_steps_lines.extend(
                [
                    f"### Step {idx}: {step.get('title', f'Step {idx}')}",
                    f"- Description: {step.get('description', 'Needs Review')}",
                    f"- Tools / Systems: {step.get('system', 'Needs Review')}",
                    f"- Inputs: {step.get('input', 'Needs Review')}",
                    f"- Outputs: {step.get('output', 'Needs Review')}",
                    f"- Source Timestamp: {step.get('source_timestamp', 'Needs Review')}",
                ]
            )
            if screenshot_path:
                process_steps_lines.append(f"![Step {idx} Screenshot]({screenshot_path})")
                if screenshot.get("reason"):
                    process_steps_lines.append(f"- Frame Reason: {screenshot.get('reason')}")
            else:
                process_steps_lines.append("- Screenshot: Not available")
            if str(step.get("note", "")).strip():
                process_steps_lines.append(f"- Note: {step.get('note')}")
            process_steps_lines.append("")
    else:
        process_steps_lines.extend(
            [
                "### Step 1: Needs Review",
                "- Description: Needs Review",
                "- Tools / Systems: Needs Review",
                "- Inputs: Needs Review",
                "- Outputs: Needs Review",
                "- Source Timestamp: Needs Review",
                "- Screenshot: Not available",
            ]
        )
    rendered = _replace_between(rendered, "## 3. Process Steps", "## 4. Process Exceptions", "\n".join(process_steps_lines))

    exception_rows = [
        "| {scenario} | {trigger} | {action} | {owner} |".format(
            scenario=row.get("scenario", "Needs Review"),
            trigger=row.get("trigger_symptom", "Needs Review"),
            action=row.get("action_to_take", "Needs Review"),
            owner=row.get("escalation_path", "Needs Review"),
        )
        for row in (exceptions.get("exception_matrix", []) if isinstance(exceptions, dict) else [])[:6]
    ] or ["| Needs Review | Needs Review | Needs Review | Needs Review |"]
    exception_block = "\n".join(
        [
            "| Exception Scenario | Description | Action Required | Owner |",
            "|--------------------|-------------|-----------------|-------|",
            *exception_rows,
        ]
    )
    rendered = _replace_between(rendered, "## 4. Process Exceptions", "## 5. Process Controls", exception_block)

    controls_rows = []
    for idx, ctrl in enumerate((controls.get("controls", []) if isinstance(controls, dict) else [])[:3], start=1):
        type_text = str(ctrl.get("type", "")).strip().lower()
        modality = "System" if "system" in type_text else "Manual"
        control_nature = "Preventive" if "preventive" in type_text else "Detective"
        controls_rows.append(
            "| C{idx} | {step_name} | {desc} | {ctype} | {nature} |".format(
                idx=idx,
                step_name=(str(ctrl.get("step_name", "")).strip() or (steps[idx - 1].get("title", f"Step {idx}") if idx - 1 < len(steps) else f"Step {idx}")),
                desc=str(ctrl.get("description", "Needs Review")),
                ctype=modality,
                nature=control_nature,
            )
        )
    if not controls_rows:
        controls_rows = ["| C1 | Step 1 | Needs Review | Manual | Detective |"]
    controls_block = "\n".join(
        [
            "| Control # | Process Step | Control Description | Manual / System | Preventive / Detective |",
            "|-----------|-------------|---------------------|-----------------|------------------------|",
            *controls_rows,
        ]
    )
    rendered = _replace_between(rendered, "## 5. Process Controls", "## 6. Approval Matrix", controls_block)

    approval_rows = [
        f"| {role_labels[0]} | Needs Review |",
        f"| {role_labels[1]} | Needs Review |",
        f"| {role_labels[2]} | Needs Review |",
    ]
    approval_block = "\n".join(["| Role | Responsibility |", "|------|----------------|", *approval_rows])
    rendered = _replace_between(rendered, "## 6. Approval Matrix", "## 7. Appendix", approval_block)

    faq_rows = [
        "| {idx} | {topic} | {tip} |".format(
            idx=idx + 1,
            topic=row.get("topic", "Needs Review"),
            tip=row.get("tip", "Needs Review"),
        )
        for idx, row in enumerate(faq_items[:3])
    ] or [
        "| {idx} | {topic} | {tip} |".format(
            idx=idx + 1,
            topic=row.get("training_module", "Needs Review"),
            tip=row.get("delivery_mode", "Needs Review"),
        )
        for idx, row in enumerate(training_rows[:3])
    ] or [
        "| 1 | Process overview | Needs Review |",
    ]
    faq_block = "\n".join(["| # | Topic | Top Tips |", "|---|-------|----------|", *faq_rows])
    rendered = _replace_between(rendered, "### Frequently Asked Questions (FAQs)", "---", faq_block)

    # Remove template-authoring notes from final user-facing output.
    rendered = re.sub(r"\n\*\*Notes for AI Usage\*\*[\s\S]*$", "", rendered, flags=re.MULTILINE)
    # Safety net: avoid leaking unresolved placeholder tokens.
    rendered = re.sub(r"<[^>\n]+>", "Needs Review", rendered)
    rendered = _collapse_duplicate_headings(rendered)
    return rendered.strip() + "\n"


def render_document_markdown(document: Dict, sipoc: List[Dict], document_type: str) -> str:
    if document_type == "custom_sop":
        return render_custom_sop_markdown(document=document, sipoc=sipoc)
    if document_type == "sop":
        return render_sop_markdown(document=document, sipoc=sipoc)
    return render_standard_pdd_markdown(pdd=document, sipoc=sipoc)
