from app.pdd_template import render_custom_sop_markdown, render_standard_pdd_markdown


def test_render_standard_pdd_markdown_contains_template_sections():
    pdd = {
        "purpose": "Validate incoming invoices.",
        "scope": "Invoice validation for AP team.",
        "triggers": ["Daily batch trigger"],
        "preconditions": ["AP mailbox access"],
        "steps": [
            {
                "step_no": "1.1",
                "title": "Open mailbox",
                "actor": "operator",
                "system": "outlook",
                "description": "Review incoming invoices.",
                "input": "email",
                "output": "invoice pdf",
            }
        ],
        "roles": ["operator"],
        "systems": ["outlook"],
        "business_rules": ["Process only invoices with PO number."],
        "exceptions": ["Duplicate invoice number."],
        "outputs": ["Validated invoice record"],
        "metrics": ["Accuracy > 98%"],
        "risks": ["OCR quality issues"],
    }
    sipoc = [
        {
            "supplier": "vendor",
            "input": "invoice email",
            "process_step": "Review incoming invoices.",
            "output": "validated invoice",
            "customer": "ap_team",
        }
    ]

    md = render_standard_pdd_markdown(pdd=pdd, sipoc=sipoc)
    assert "## 1. Document Control" in md
    assert "## 5. Detailed Process Steps (As-Is)" in md
    assert "## 9. Metrics & Risks" in md


def test_render_standard_pdd_markdown_uses_template_path_env(tmp_path, monkeypatch):
    custom = tmp_path / "custom_template.md"
    custom.write_text(
        "\n".join(
            [
                "# [Process Name] - Process Definition Document (PDD)",
                "",
                "## 1. Document Control",
                "| Version | Date | Author | Description |",
                "| :--- | :--- | :--- | :--- |",
                "| 1.0 | 2026-03-05 | [Author Name] | Initial Draft (As-Is Process) |",
                "",
                "## 2. Process Overview",
                "*   **Process Name:** [e.g., Invoice Validation]",
                "",
                "## 3. Scope",
                "### 3.1 In-Scope",
                "*   [e.g., Processing PDF invoices from the 'AP_Inbox']",
                "",
                "### 3.2 Out-of-Scope",
                "*   [e.g., Physical paper invoices]",
                "",
                "## 4. Prerequisites & Systems",
                "### 4.1 Prerequisites",
                "*   [e.g., Access to Shared Drive]",
                "",
                "### 4.2 Application Inventory",
                "| Application | Version | Access Method |",
                "| :--- | :--- | :--- |",
                "| Internal Portal | v1.2 | Chrome/Edge |",
                "",
                "---",
                "",
                "## 5. Detailed Process Steps (As-Is)",
                "| Step # | Action | Role | System | Input | Output |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
                "| 1.1 | Placeholder | Operator | Manual | In | Out |",
                "",
                "## 6. Business Rules & Logic",
                "*Define the 'brains' of the process.*",
                "",
                "## 7. Exceptions Handling",
                "### 7.1 Business Exceptions",
                "*   None",
                "",
                "### 7.2 Technical Exceptions",
                "*   None",
                "",
                "## 8. Inputs & Outputs",
                "*   **Primary Input:** Input",
                "*   **Primary Output:** Output",
                "",
                "## 9. Metrics & Risks",
                "*   **Success Metric:** Metric",
                "*   **Risk:** Risk",
                "",
                "---",
                "**Document generated for Process Excellence / Automation Readiness.**",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PDD_TEMPLATE_PATH", str(custom))

    md = render_standard_pdd_markdown(
        pdd={
            "purpose": "Test objective",
            "scope": "Test scope",
            "triggers": [],
            "preconditions": [],
            "steps": [],
            "roles": [],
            "systems": [],
            "business_rules": [],
            "exceptions": [],
            "outputs": [],
            "metrics": [],
            "risks": [],
        },
        sipoc=[],
    )

    assert "Process Definition Document (PDD)" in md
    assert "## 8. Inputs & Outputs" in md


def test_render_custom_sop_markdown_uses_root_template(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {"sop_title": "Invoice Validation SOP", "department": "Finance", "version": "1.2"},
            "purpose": "Validate invoices before posting.",
            "scope": {"in_scope": ["Invoice validation"]},
            "process_overview": {"flow_summary": "Receive -> Validate -> Post"},
            "steps": [{"title": "Receive Invoice"}, {"title": "Validate Invoice"}],
            "roles_and_responsibilities": [{"role": "AP Analyst"}],
            "exception_handling": {"exception_matrix": [{"scenario": "Missing PO", "trigger_symptom": "PO absent", "action_to_take": "Reject"}]},
            "controls_and_compliance": {"controls": [{"description": "Dual control check"}]},
            "quality_checks": {"checks": [{"check_id": "QC-01"}]},
            "training_and_kt": {"training_requirements": [{"training_module": "SOP Walkthrough", "delivery_mode": "Classroom"}]},
            "prerequisites_and_inputs": {"input_documents_data": [{"frequency": "Daily"}]},
            "sla_and_performance_targets": [{"kpi": "TAT", "target": "< 1 day"}],
        },
        sipoc=[{"supplier": "Vendor", "input": "Invoice", "process_step": "Validate", "output": "Approved Invoice", "customer": "Finance"}],
    )
    assert "## Index" in md
    assert "## 2.6 SIPOC" in md
    assert "Invoice Validation SOP" in md
