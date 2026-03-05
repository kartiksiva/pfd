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
