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
    assert "# Standard Operating Procedure (SOP)" in md
    assert "SOP Template" not in md
    assert "**SOP Format**" not in md
    assert "**Notes for AI Usage**" not in md
    assert "<Process Name>" not in md
    assert md.count("## 3. Process Steps") == 1


def test_render_custom_sop_markdown_preserves_evidence_grounded_sections(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Customer Complaint Intake and Resolution Triage",
                "department": "Customer Service",
                "process_owner": "Customer Service Analyst",
                "version": "1.0",
                "effective_date": "15-Mar-2026",
                "status": "Draft",
            },
            "purpose": "Receive, validate, categorize, and assign complaints in line with SLA and compliance requirements.",
            "scope": {"in_scope": ["Complaint intake, categorization, assignment, and tracking updates."]},
            "process_overview": {"flow_summary": "Receive -> Validate -> Categorize -> Assign -> Update tracking"},
            "steps": [
                {
                    "title": "Receive and Consolidate Complaints",
                    "description": "Review Outlook mailbox, phone log, and CRM-fed channels.",
                    "system": "Outlook, Excel, CRM",
                    "input": "Complaint details",
                    "output": "Complaint record in CRM",
                    "source_timestamp": "",
                }
            ],
            "roles_and_responsibilities": [{"role": "Customer Service Analyst", "responsibility": "Execute intake and triage steps"}],
            "exception_handling": {
                "exception_matrix": [
                    {
                        "scenario": "Customer does not respond to requests for additional information.",
                        "trigger_symptom": "Observed in transcript or operating discussion",
                        "action_to_take": "Send reminder, track pending customer response, and escalate per SLA if still unresolved.",
                        "escalation_path": "Needs Review",
                    }
                ]
            },
            "controls_and_compliance": {
                "controls": [{"description": "There is a manual override and compliance requires an audit trail."}],
                "policies": ["Compliance review is required for regulatory complaint handling."],
            },
            "quality_checks": {"checks": [{"check_id": "QC-01"}]},
            "training_and_kt": {"training_requirements": [{"training_module": "Complaint handling overview", "delivery_mode": "Workshop"}]},
            "prerequisites_and_inputs": {"input_documents_data": [{"frequency": "Daily (Around 180 to 220 complaints per day on average.)"}]},
            "sla_and_performance_targets": [{"kpi": "Regulatory complaints", "target": "Need response within 24 hours."}],
            "tools_and_systems_reference": [{"tool_system": "CRM"}, {"tool_system": "ERP"}],
        },
        sipoc=[{"supplier": "Customer", "input": "Complaint details", "process_step": "Receive and Consolidate Complaints", "output": "Complaint record in CRM", "customer": "Customer Service Analyst"}],
    )
    assert "Customer Complaint Intake and Resolution Triage" in md
    assert "**Function:** Customer Service" in md
    assert "24 hours" in md
    assert md.count("## 3. Process Steps") == 1
    assert "needs.review@example.com" not in md
    assert "Execute assigned steps" not in md


def test_render_custom_sop_markdown_uses_conservative_raci_and_approval_defaults(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Complaint Intake SOP",
                "department": "Complaint Management",
                "process_owner": "Customer Service Analyst",
                "version": "1.0",
                "effective_date": "15-Mar-2026",
                "status": "Draft",
            },
            "purpose": "Manage complaint intake.",
            "scope": {"in_scope": ["Complaint intake."]},
            "process_overview": {"flow_summary": "Receive -> Validate -> Assign"},
            "steps": [
                {"title": "Receive Complaint", "actor": "Customer Service Analyst"},
                {"title": "Validate Complaint", "actor": "Customer Service Analyst"},
                {"title": "Assign Complaint", "actor": "Compliance Team"},
            ],
            "roles_and_responsibilities": [
                {"role": "Customer Service Analyst", "responsibility": "Manage intake."},
                {"role": "Compliance Team", "responsibility": "Review regulatory complaints."},
            ],
            "exception_handling": {"exception_matrix": []},
            "controls_and_compliance": {"controls": []},
        },
        sipoc=[],
    )
    assert "| Task / Stakeholders | Customer Service Analyst | Compliance Team |" in md
    assert "| Receive Complaint | R | Needs Review |" in md
    assert "| Compliance Team | Needs Review |" in md
    assert "| 1 | Customer Service Analyst | Needs Review | Needs Review |" in md


def test_render_custom_sop_markdown_hides_placeholder_role_columns(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "RPA Challenge Data Entry",
                "department": "Needs Review",
                "process_owner": "Automation Bot",
                "version": "1.0",
                "effective_date": "16-Mar-2026",
                "status": "Draft",
            },
            "purpose": "Document current process flow from submitted evidence.",
            "scope": {"in_scope": ["Challenge execution flow."]},
            "process_overview": {"flow_summary": "Download -> Start -> Submit"},
            "steps": [
                {"title": "Download Input Spreadsheet", "actor": "Automation Bot"},
                {"title": "Start Challenge", "actor": "Automation Bot"},
                {"title": "Submit Form", "actor": "Automation Bot"},
            ],
            "roles_and_responsibilities": [{"role": "Automation Bot"}],
            "exception_handling": {"exception_matrix": []},
            "controls_and_compliance": {"controls": []},
        },
        sipoc=[],
    )
    assert "| Task / Stakeholders | Automation Bot |" in md
    assert "| Download Input Spreadsheet | R |" in md
    assert "| Needs Review | Needs Review |" not in md.split("## 6. Approval Matrix", 1)[1]


def test_render_custom_sop_markdown_shows_effort_and_automation_opportunities(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Complaint Intake SOP",
                "department": "Needs Review",
                "process_owner": "Intake Analyst",
                "version": "1.0",
                "effective_date": "16-Mar-2026",
                "status": "Draft",
            },
            "purpose": "Document current process flow from submitted evidence.",
            "scope": {"in_scope": ["Complaint intake and triage."]},
            "process_overview": {"flow_summary": "Receive -> Validate -> Assign"},
            "steps": [
                {
                    "title": "Complaint Intake",
                    "actor": "Intake Analyst",
                    "description": "Receive customer complaint.",
                    "system": "CRM",
                    "input": "Customer complaint",
                    "output": "Complaint record",
                    "effort_minutes_min": 8,
                    "effort_minutes_max": 10,
                }
            ],
            "roles_and_responsibilities": [{"role": "Intake Analyst"}],
            "exception_handling": {"exception_matrix": []},
            "controls_and_compliance": {"controls": []},
            "automation_opportunities": [
                {
                    "opportunity_id": "AUTO-01",
                    "description": "Manual rework during complaint intake",
                    "quantification": "8 to 10 minutes per complaint",
                    "automation_signal": "high",
                }
            ],
        },
        sipoc=[],
    )
    assert "- Estimated Effort: 8-10 minutes" in md
    assert "### Automation Opportunities" in md
    assert "Manual rework during complaint intake" in md


def test_render_custom_sop_markdown_formats_sla_targets_and_control_step_names(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Complaint Intake SOP",
                "department": "Complaint Management",
                "process_owner": "Needs Review",
                "version": "1.0",
                "effective_date": "15-Mar-2026",
                "status": "Draft",
            },
            "purpose": "Manage complaint intake.",
            "scope": {"in_scope": ["Complaint intake."]},
            "process_overview": {"flow_summary": "Receive -> Categorize -> Assign"},
            "steps": [
                {"title": "Receive Complaint", "actor": "Complaint Resolution Analyst"},
                {"title": "Categorize Complaint", "actor": "Complaint Resolution Analyst"},
                {"title": "Assign Complaint", "actor": "Complaint Resolution Analyst"},
            ],
            "roles_and_responsibilities": [
                {"role": "Complaint Resolution Analyst", "responsibility": "Needs Review"},
                {"role": "Customer Service Analyst", "responsibility": "Needs Review"},
                {"role": "Compliance Team", "responsibility": "Needs Review"},
            ],
            "sla_and_performance_targets": [
                {"kpi": "Regulatory complaints", "target": "Response within 24 hours"},
                {"kpi": "Standard complaints", "target": "Acknowledgement within 3 business days"},
            ],
            "controls_and_compliance": {
                "controls": [
                    {
                        "description": "Complaint categorization must support the correct SLA path, including regulatory response timelines and standard acknowledgement targets.",
                        "type": "Manual Detective",
                        "step_name": "Categorize Complaint",
                    }
                ]
            },
        },
        sipoc=[],
    )
    assert "Regulatory complaints: Response within 24 hours; Standard complaints: Acknowledgement within 3 business days" in md
    assert "| C1 | Categorize Complaint | Complaint categorization must support the correct SLA path" in md


def test_render_custom_sop_markdown_uses_custom_summary_notes_and_faq(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Customer Complaint Intake and Resolution Triage",
                "department": "Complaint Management",
                "process_owner": "Complaint Resolution Analyst",
                "version": "1.0",
                "effective_date": "16-Mar-2026",
                "status": "Draft",
            },
            "purpose": "Manage complaint intake and triage.",
            "scope": {"in_scope": ["Complaint intake and assignment."]},
            "process_overview": {"flow_summary": "Receive -> Categorize -> Assign -> Update tracker"},
            "steps": [
                {
                    "title": "Assign Complaint to Resolution Team",
                    "actor": "Complaint Resolution Analyst",
                    "description": "Assign the complaint and copy Compliance for regulatory complaints.",
                    "note": "For regulatory complaints, copy the Compliance Team during assignment so the 24-hour response requirement is visible.",
                },
                {
                    "title": "Update Management Tracking Spreadsheet",
                    "actor": "Customer Service Analyst",
                    "description": "Update the management tracking spreadsheet.",
                    "note": "Keep the management tracking spreadsheet aligned with the CRM record to support reporting consistency.",
                },
            ],
            "roles_and_responsibilities": [
                {"role": "Complaint Resolution Analyst"},
                {"role": "Customer Service Analyst"},
                {"role": "Compliance Team"},
            ],
            "exception_handling": {"exception_matrix": []},
            "controls_and_compliance": {"controls": []},
            "custom_sop_summary": {
                "suppliers": ["Customer", "Call Team Agent", "Complaint Resolution Analyst"],
                "inputs": ["Customer complaint via email, web form, portal, or phone", "Phone complaint details in a spreadsheet", "Unvalidated complaint record", "Customer evidence and attachments"],
                "outputs": ["Complaint record in CRM", "Categorized complaint record", "Assigned complaint record", "Regulatory complaint notification to Compliance Team", "Updated management tracking spreadsheet"],
                "customers": ["Resolution Teams (Billing, Product Support, Field Service)", "Compliance Team", "Management"],
            },
            "faq_items": [
                {
                    "topic": "Strategic or escalated accounts",
                    "tip": "Review the assignment step for special routing exceptions; detailed routing rules need review.",
                }
            ],
        },
        sipoc=[],
    )
    assert "Customer evidence and attachments" in md
    assert "Categorized complaint record" in md
    assert "Assigned complaint record" in md
    assert "Unvalidated complaint record" in md
    assert "Acknowledgment email sent" not in md
    assert "- Note: For regulatory complaints, copy the Compliance Team during assignment so the 24-hour response requirement is visible." in md
    assert "- Note: Keep the management tracking spreadsheet aligned with the CRM record to support reporting consistency." in md
    assert "| 1 | Strategic or escalated accounts | Review the assignment step for special routing exceptions; detailed routing rules need review. |" in md


def test_render_custom_sop_markdown_preserves_grounded_roles_and_scope(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Customer Complaint Intake and Resolution Triage",
                "department": "Customer Service",
                "process_owner": "Complaint Resolution Analyst",
                "version": "1.0",
                "effective_date": "16-Mar-2026",
                "status": "Draft",
            },
            "purpose": "To receive, validate, categorize, and assign incoming customer complaints to the appropriate resolution team in a timely and compliant manner.",
            "scope": {"in_scope": ["The process begins when a customer complaint is received through any channel and ends when the complaint is validated, categorized, and assigned to a resolution team."]},
            "process_overview": {"flow_summary": "Complaint Intake -> Complaint Assignment"},
            "steps": [
                {"title": "Complaint Intake", "actor": "Complaint Resolution Analyst"},
                {"title": "Complaint Assignment", "actor": "Complaint Resolution Analyst"},
            ],
            "roles_and_responsibilities": [
                {"role": "Complaint Resolution Analyst"},
                {"role": "Customer Service Analyst"},
                {"role": "Compliance Team"},
            ],
            "exception_handling": {"exception_matrix": []},
            "controls_and_compliance": {"controls": []},
        },
        sipoc=[],
    )
    assert "**Sub-Function:** Complaint Resolution Analyst" in md
    assert "| 1 | Complaint Resolution Analyst | Needs Review | Needs Review |" in md
    assert "| 2 | Customer Service Analyst | Needs Review | Needs Review |" in md
    assert "| 3 | Compliance Team | Needs Review | Needs Review |" in md
    assert "### 2.2 Process Objective\n- To receive, validate, categorize, and assign incoming customer complaints" in md
    assert "closure" not in md.lower()


def test_render_custom_sop_markdown_uses_only_purpose_in_objective_section(monkeypatch):
    monkeypatch.delenv("CUSTOM_SOP_TEMPLATE_PATH", raising=False)
    md = render_custom_sop_markdown(
        document={
            "document_control": {
                "sop_title": "Customer Complaint Intake and Resolution Triage",
                "department": "Customer Service",
                "process_owner": "Complaint Resolution Analyst",
                "version": "1.0",
                "effective_date": "16-Mar-2026",
                "status": "Draft",
            },
            "purpose": "To receive, validate, categorize, and assign incoming customer complaints to the appropriate resolution team in a timely and compliant manner.",
            "scope": {"in_scope": ["Complaint intake, categorization, assignment, and tracking updates."]},
            "process_overview": {"flow_summary": "Receive -> Validate -> Categorize -> Assign"},
            "steps": [{"title": "Complaint Intake", "actor": "Complaint Resolution Analyst"}],
            "roles_and_responsibilities": [{"role": "Complaint Resolution Analyst"}],
            "exception_handling": {"exception_matrix": []},
            "controls_and_compliance": {"controls": []},
        },
        sipoc=[],
    )
    objective_section = md.split("### 2.2 Process Objective", 1)[1].split("---", 1)[0]
    assert "To receive, validate, categorize, and assign incoming customer complaints" in objective_section
    assert "Complaint intake, categorization, assignment, and tracking updates." not in objective_section
    assert "Ensure consistent execution with controls and exception handling." not in objective_section
