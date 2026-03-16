from app.pipelines.document_generation import PDD_SECTION_ORDER, generate_document_from_extraction, generate_pdd_document, generate_sipoc_rows
from app.pipelines.process_extraction import extract_process_structure
from app.pipelines.quality_checks import run_quality_checks


COMPLAINT_TRANSCRIPT = """
Customer complaints can come in through email, web form, customer support portal, or by phone.
Around 180 to 220 complaints per day on average. Mondays are higher.
Regulatory complaints need response within 24 hours, while standard complaints allow 3 business days for acknowledgement.
Analysts manually assign the complaint to billing operations, product support, or field service. Regulatory complaints are also copied to compliance.
Outlook shared mailbox, Excel phone log, CRM, a document repository for evidence, and sometimes ERP are involved.
Around 20 percent of complaints are assigned to the wrong team initially.
Initial intake and setup takes 8 to 10 minutes. For incomplete complaints, it can take 15 minutes or more.
There is a manual override and compliance requires an audit trail.
""".strip()


def _sample_extraction():
    return {
        "process_steps": [
            {
                "step_no": 1,
                "title": "Step 1",
                "summary": "Customer submits request",
                "sources": ["transcript"],
                "confidence": 0.7,
                "role": "customer",
                "system": "manual_or_unspecified",
            },
            {
                "step_no": 2,
                "title": "Step 2",
                "summary": "Analyst validates request",
                "sources": ["transcript"],
                "confidence": 0.72,
                "role": "analyst",
                "system": "manual_or_unspecified",
            },
            {
                "step_no": 3,
                "title": "Step 3",
                "summary": "System updates ticket",
                "sources": ["transcript", "video"],
                "confidence": 0.8,
                "role": "system",
                "system": "ticketing_system",
            },
        ],
        "roles": ["analyst", "customer", "system"],
        "systems": ["manual_or_unspecified", "ticketing_system"],
        "handoffs": [],
        "business_rules": [],
        "exceptions": [],
        "outputs": [],
        "metrics": [],
        "risks": [],
        "confidence": 0.76,
    }


def test_generate_pdd_document_has_deterministic_section_order():
    pdd = generate_pdd_document(_sample_extraction())
    assert list(pdd.keys()) == PDD_SECTION_ORDER
    assert len(pdd["steps"]) == 3


def test_generate_sipoc_rows_handoff_continuity():
    sipoc = generate_sipoc_rows(_sample_extraction())
    assert len(sipoc) >= 2
    for i in range(len(sipoc) - 1):
        assert sipoc[i]["customer"] == sipoc[i + 1]["supplier"]


def test_quality_checks_flag_low_confidence_and_missing_sipoc():
    pdd = generate_pdd_document(_sample_extraction())
    result = run_quality_checks(pdd=pdd, sipoc=[], confidence=0.2)
    assert result["quality_score"] < 0.2
    types = {f["type"] for f in result["flags"]}
    assert "low_confidence" in types
    assert "missing_sipoc" in types


def test_extract_process_structure_filters_internal_pipeline_action_labels():
    extraction = extract_process_structure(
        {
            "merged_steps": [
                {"summary": "segment_process_frames", "sources": ["video"], "confidence": 0.68},
                {"summary": "infer_activity_timeline", "sources": ["audio"], "confidence": 0.68},
                {"summary": "Visual cues detected during process walkthrough.", "sources": ["video"], "confidence": 0.6},
            ],
            "confidence": 0.35,
        }
    )

    summaries = [step["summary"] for step in extraction["process_steps"]]
    assert "segment_process_frames" not in summaries
    assert "infer_activity_timeline" not in summaries
    assert any("business action" in summary.lower() for summary in summaries)
    assert any("business step" in summary.lower() for summary in summaries)


def test_extract_process_structure_preserves_operational_facts_from_transcript():
    extraction = extract_process_structure(
        {
            "merged_steps": [
                {"summary": "Receive and consolidate complaints", "sources": ["transcript"], "confidence": 0.7},
                {"summary": "Validate complaint for completeness", "sources": ["transcript"], "confidence": 0.7},
                {"summary": "Assign complaint to resolution team", "sources": ["transcript"], "confidence": 0.7},
            ],
            "transcript_text": COMPLAINT_TRANSCRIPT,
            "confidence": 0.8,
        }
    )

    facts = extraction["operational_facts"]
    assert facts["frequency"] == "Daily"
    assert any("24 hours" in item for item in facts["sla_targets"])
    assert any("180 to 220 complaints per day" in item for item in facts["volumes_or_frequency"])
    assert "CRM" in extraction["systems"]
    assert "Outlook" in extraction["systems"]
    assert any("20 percent" in item for item in extraction["metrics"])


def test_generate_document_from_extraction_avoids_generic_step_title_for_sop_title():
    extraction = _sample_extraction()
    extraction["process_name"] = "Invoice Reconciliation"
    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert doc["document_control"]["sop_title"] == "Invoice Reconciliation"


def test_generate_document_from_extraction_uses_neutral_defaults_for_sop_metadata():
    extraction = _sample_extraction()
    extraction["process_name"] = "Customer Complaint Intake and Resolution Triage"
    extraction["roles"] = ["Customer Service Analyst", "Compliance Team"]
    extraction["systems"] = ["CRM"]
    extraction["operational_facts"] = {
        "frequency": "Daily",
        "volumes_or_frequency": ["Around 180 to 220 complaints per day on average."],
        "sla_targets": [
            "Regulatory complaints need response within 24 hours.",
            "Standard complaints allow 3 business days for acknowledgement.",
        ],
        "routing_rules": ["Analysts manually assign the complaint to billing operations, product support, or field service."],
        "control_requirements": ["There is a manual override and compliance requires an audit trail."],
        "governance_notes": ["Compliance will need to review any proposed rules for regulatory complaint handling."],
        "quantified_pain_points": ["Around 20 percent of complaints are assigned to the wrong team initially."],
        "systems": ["CRM", "Outlook", "Excel", "Document repository", "ERP"],
        "teams": ["Customer Service Analyst", "Compliance Team", "Billing Operations"],
        "exception_details": ["Customer does not respond to requests for additional information."],
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert doc["document_control"]["sop_title"] == "Customer Complaint Intake and Resolution Triage"
    assert doc["document_control"]["department"] == "Needs Review"
    assert "180 to 220 complaints per day" in doc["prerequisites_and_inputs"]["input_documents_data"][0]["frequency"]
    assert any("24 hours" in row["target"] for row in doc["sla_and_performance_targets"])
    tool_names = [row["tool_system"] for row in doc["tools_and_systems_reference"]]
    assert "ERP" in tool_names
    role_rows = doc["roles_and_responsibilities"]
    assert any(row["responsibility"] != "Execute assigned steps" for row in role_rows)
    assert any("audit trail" in row["description"].lower() for row in doc["controls_and_compliance"]["controls"])


def test_generate_document_from_extraction_filters_future_state_control_noise():
    extraction = _sample_extraction()
    extraction["process_name"] = "Customer Complaint Intake and Resolution Triage"
    extraction["roles"] = ["Customer Service Analyst", "Compliance Team"]
    extraction["operational_facts"] = {
        "frequency": "Daily",
        "volumes_or_frequency": ["Around 180 to 220 complaints per day on average."],
        "sla_targets": ["Regulatory complaints need response within 24 hours."],
        "routing_rules": [],
        "control_requirements": [
            "From a compliance standpoint, this process matters because we have SLA commitments and regulatory response timelines for certain complaint categories.",
            "Would it be acceptable to have all complaint sources normalized into a single intake queue, with mandatory-field validation, standardized acknowledgment templates, rules-based categorization suggestions, and assignment recommendations?",
            "As long as the audit trail is preserved and we can show what was sent and when.",
        ],
        "governance_notes": [],
        "quantified_pain_points": [],
        "systems": ["CRM"],
        "teams": ["Customer Service Analyst", "Compliance Team"],
        "exception_details": [],
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    descriptions = [row["description"] for row in doc["controls_and_compliance"]["controls"]]
    assert any("audit trail" in item.lower() for item in descriptions)
    assert not any("single intake queue" in item.lower() for item in descriptions)
    assert not any("would it be acceptable" in item.lower() for item in descriptions)


def test_generate_document_from_extraction_dedupes_and_cleans_exception_rows():
    extraction = _sample_extraction()
    extraction["process_name"] = "Customer Complaint Intake and Resolution Triage"
    extraction["roles"] = ["Customer Service Analyst", "Complaint Resolution Analyst", "Compliance Team"]
    extraction["operational_facts"] = {
        "frequency": "Daily",
        "volumes_or_frequency": [],
        "sla_targets": [],
        "routing_rules": [],
        "control_requirements": [],
        "governance_notes": [],
        "quantified_pain_points": [],
        "systems": ["CRM"],
        "teams": ["Customer Service Analyst"],
        "exception_details": [
            "**Meera Iyer:** What happens if information is missing?",
            "**Anita Rao:** Not really. We have guidance in a training deck, but it is not a strict rulebook. Experienced analysts do it well, but newer team members often misclassify complaints.",
            "**Vivek Menon:** Misclassification affects SLA handling. Regulatory complaints need response within 24 hours, while standard complaints allow 3 business days for acknowledgement.",
        ],
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    exception_rows = doc["exception_handling"]["exception_matrix"]
    assert len(exception_rows) == 1
    assert exception_rows[0]["scenario"] == "Work item is routed or classified incorrectly."
    assert exception_rows[0]["trigger_symptom"] == "Existing guidance is informal, so newer team members may classify complaints inconsistently."
    assert "Anita Rao:" not in exception_rows[0]["trigger_symptom"]
    assert "What happens if information is missing?" not in str(exception_rows)


def test_generate_document_from_extraction_custom_sop_preserves_explicit_evidence_without_extra_domain_defaults():
    extraction = {
        "process_name": "Customer Complaint Intake and Resolution Triage",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Intake and Manual Case Creation",
                "summary": "Analyst reviews the shared email mailbox and phone log spreadsheet, then creates a complaint record in CRM.",
                "role": "Complaint Intake Analyst",
                "system": "Outlook, Excel, CRM",
                "input": "Complaint via email, web form, portal, or phone",
                "output": "Complaint record in CRM",
            },
            {
                "step_no": 2,
                "title": "Categorize Complaint",
                "summary": "Analyst selects complaint type in CRM based on available details.",
                "role": "Complaint Resolution Analyst",
                "system": "CRM",
                "input": "Unvalidated complaint record",
                "output": "Categorized complaint record",
            },
            {
                "step_no": 3,
                "title": "Assign Complaint to Resolution Team",
                "summary": "Analyst assigns the complaint and copies Compliance for regulatory complaints.",
                "role": "Complaint Resolution Analyst",
                "system": "CRM",
                "input": "Categorized complaint record",
                "output": "Assigned complaint record",
            },
            {
                "step_no": 4,
                "title": "Update Management Tracking Spreadsheet",
                "summary": "Analyst updates the management tracking spreadsheet used for reporting.",
                "role": "Customer Service Analyst",
                "system": "Excel",
                "input": "Assigned complaint details",
                "output": "Updated tracking spreadsheet",
            },
            {
                "step_no": 5,
                "title": "Acknowledgment Email",
                "summary": "Analyst sends an acknowledgment email to the customer.",
                "role": "Complaint Intake Analyst",
                "system": "Outlook, CRM",
                "input": "Complaint record",
                "output": "Acknowledgment email sent",
            },
        ],
        "roles": ["Complaint Intake Analyst", "Complaint Resolution Analyst", "Customer Service Analyst", "Compliance Team"],
        "systems": ["CRM", "Outlook", "Excel", "Document repository"],
        "business_rules": [],
        "exceptions": [],
        "outputs": [],
        "metrics": [],
        "risks": [],
        "operational_facts": {
            "frequency": "Daily",
            "volumes_or_frequency": ["Around 180 to 220 complaints per day on average."],
            "sla_targets": ["Regulatory complaints need response within 24 hours.", "Standard complaints allow 3 business days for acknowledgement."],
            "routing_rules": ["There are exceptions for strategic customers and escalated accounts."],
            "control_requirements": ["As long as the audit trail is preserved and we can show what was sent and when."],
            "governance_notes": [],
            "quantified_pain_points": [],
            "systems": ["CRM", "Outlook", "Excel", "Document repository"],
            "teams": ["Complaint Resolution Analyst", "Customer Service Analyst", "Compliance Team", "Call Team Agent", "Management"],
            "exception_details": [],
        },
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    step_titles = [step["title"] for step in doc["steps"]]
    assert "Acknowledgment Email" in step_titles
    assert "Complaint Resolution Analyst" in [row["role"] for row in doc["roles_and_responsibilities"]]
    assert doc["custom_sop_summary"]["inputs"][0] == "Complaint via email, web form, portal, or phone"
    assert "Customer evidence and attachments" not in doc["custom_sop_summary"]["inputs"]
    assert "Categorized complaint record" in doc["custom_sop_summary"]["outputs"]
    assert "Assigned complaint record" in doc["custom_sop_summary"]["outputs"]
    assert not any(step.get("note") for step in doc["steps"])
    assert doc["faq_items"][0]["topic"] == "Process overview"
    assert doc["document_control"]["process_owner"] == "Complaint Intake Analyst"
    assert doc["purpose"] == "Document current process flow from submitted evidence"
    assert doc["scope"]["out_of_scope"][0] == "Activities outside the documented current-state process boundary."


def test_generate_document_from_extraction_discards_transcript_scope_overreach_and_weak_review_control():
    extraction = {
        "process_name": "Customer Complaint Intake and Resolution Triage",
        "purpose": "To receive, validate, categorize, assign, track, and close customer complaints in compliance with SLA and regulatory requirements.",
        "scope": "Covers all customer complaints from initial intake through resolution assignment and closure. Excludes final resolution and post-resolution follow-up.",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Complaint Intake",
                "summary": "Analysts review mailbox and phone log, then create complaint records in CRM.",
                "role": "Intake Analyst",
                "system": "CRM",
                "input": "Customer complaint",
                "output": "Complaint record in CRM",
            },
            {
                "step_no": 2,
                "title": "Assignment to Resolution Team",
                "summary": "Complaint is manually assigned to the appropriate resolution team.",
                "role": "Intake Analyst",
                "system": "CRM",
                "input": "Categorized complaint record",
                "output": "Assigned complaint record",
            },
        ],
        "roles": ["Intake Analyst", "Customer Service Analyst", "Compliance Team"],
        "systems": ["CRM", "Outlook"],
        "operational_facts": {
            "frequency": "Daily",
            "volumes_or_frequency": [],
            "sla_targets": ["Regulatory complaints need response within 24 hours."],
            "routing_rules": [],
            "control_requirements": ["There is a manual override and compliance requires an audit trail."],
            "governance_notes": [],
            "quantified_pain_points": [],
            "systems": ["CRM", "Outlook"],
            "teams": ["Intake Analyst", "Customer Service Analyst", "Compliance Team"],
            "exception_details": [],
        },
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert doc["purpose"] == "To receive, validate, categorize, assign, track, and close customer complaints in compliance with SLA and regulatory requirements"
    assert doc["scope"]["in_scope"][0] == "The process begins at the documented trigger and ends when the final documented output is produced."
    descriptions = [row["description"] for row in doc["controls_and_compliance"]["controls"]]
    assert any("audit trail" in item.lower() for item in descriptions)
    assert not any("approval" in item.lower() for item in descriptions)


def test_generate_document_from_extraction_surfaces_effort_and_automation_opportunities():
    extraction = {
        "process_name": "Customer Complaint Intake and Resolution Triage",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Complaint Intake",
                "summary": "Receive complaint from intake channels.",
                "role": "Intake Analyst",
                "system": "CRM",
                "input": "Customer complaint",
                "output": "Complaint record",
            }
        ],
        "roles": ["Intake Analyst"],
        "systems": ["CRM"],
        "effort_data": [{"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10}],
        "pain_points": [
            {
                "description": "Complaint intake requires duplicate data entry.",
                "quantification": "8 to 10 minutes per complaint",
                "automation_signal": "high",
            }
        ],
        "operational_facts": {
            "frequency": "Daily",
            "volumes_or_frequency": [],
            "sla_targets": [],
            "routing_rules": [],
            "control_requirements": [],
            "governance_notes": [],
            "quantified_pain_points": [],
            "systems": [],
            "teams": [],
            "exception_details": [],
        },
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert doc["steps"][0]["effort_minutes_min"] == 8
    assert doc["steps"][0]["effort_minutes_max"] == 10
    assert doc["automation_opportunities"][0]["description"] == "Complaint intake requires duplicate data entry"


def test_generate_document_from_extraction_preserves_effort_by_step_number_after_custom_step_filtering():
    extraction = {
        "process_name": "Customer Complaint Intake and Resolution Triage",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Complaint Intake",
                "summary": "Receive complaint from intake channels.",
                "role": "Intake Analyst",
                "system": "CRM",
                "input": "Customer complaint",
                "output": "Complaint record",
            },
            {
                "step_no": 2,
                "title": "Recommended Automation Path",
                "summary": "Recommended future-state automation for intake routing.",
                "role": "System",
                "system": "Workflow Engine",
                "input": "Complaint record",
                "output": "Auto-routed complaint",
            },
            {
                "step_no": 3,
                "title": "Mandatory Field Validation",
                "summary": "Validate required complaint fields in CRM.",
                "role": "Intake Analyst",
                "system": "CRM",
                "input": "Complaint record",
                "output": "Validated complaint record",
            },
        ],
        "roles": ["Intake Analyst"],
        "systems": ["CRM"],
        "effort_data": [
            {"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10},
            {"step_no": 3, "effort_minutes_min": 5, "effort_minutes_max": 8},
        ],
        "pain_points": [],
        "operational_facts": {
            "frequency": "Daily",
            "volumes_or_frequency": [],
            "sla_targets": [],
            "routing_rules": [],
            "control_requirements": [],
            "governance_notes": [],
            "quantified_pain_points": [],
            "systems": [],
            "teams": [],
            "exception_details": [],
        },
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert len(doc["steps"]) == 2
    assert doc["steps"][0]["title"] == "Complaint Intake"
    assert doc["steps"][0]["effort_minutes_min"] == 8
    assert doc["steps"][0]["effort_minutes_max"] == 10
    assert doc["steps"][1]["title"] == "Mandatory Field Validation"
    assert doc["steps"][1]["effort_minutes_min"] == 5
    assert doc["steps"][1]["effort_minutes_max"] == 8


def test_generate_document_from_extraction_cleans_up_complaint_step_boundary_overlap():
    extraction = {
        "process_name": "Customer Complaint Intake and Resolution Triage",
        "purpose": "Manage complaint intake and triage.",
        "scope": "Complaint intake and triage.",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Complaint Intake and Record Creation",
                "summary": "Analysts review incoming complaints from email, web form, portal, and phone logs. Complaints not already in CRM are manually entered. Mandatory fields are checked.",
                "role": "Complaint Analyst",
                "system": "CRM, Outlook shared mailbox, Excel phone log",
                "input": "Customer complaint",
                "output": "Complaint record in CRM",
            },
            {
                "step_no": 2,
                "title": "Data Validation and Follow-up",
                "summary": "Analyst checks for mandatory fields (customer ID, product, issue category, date, contact info).",
                "role": "Complaint Analyst",
                "system": "CRM, Outlook",
                "input": "Complaint record",
                "output": "Validated complaint record or follow-up request sent",
            },
        ],
        "roles": ["Complaint Analyst"],
        "systems": ["CRM", "Outlook"],
        "operational_facts": {"frequency": "Daily", "volumes_or_frequency": [], "sla_targets": [], "routing_rules": [], "control_requirements": [], "governance_notes": [], "quantified_pain_points": [], "systems": [], "teams": [], "exception_details": []},
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert "Mandatory fields are checked" not in doc["steps"][0]["description"]
    assert "mandatory fields" in doc["steps"][1]["description"].lower()
    assert "follow-up email" in doc["steps"][1]["description"].lower()


def test_generate_document_from_extraction_custom_sop_stays_generic_for_non_domain_specific_processes():
    extraction = {
        "process_name": "RPA Challenge Data Entry Process",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Download Input Excel",
                "summary": "Download the Excel file from the challenge page.",
                "role": "RPA User",
                "system": "RPA Challenge Platform",
                "input": "Challenge web page",
                "output": "Excel input file",
            },
            {
                "step_no": 2,
                "title": "Start Challenge",
                "summary": "Click Start to begin the timed challenge.",
                "role": "RPA User",
                "system": "RPA Challenge Platform",
                "input": "Excel input file",
                "output": "Challenge timer starts",
            },
            {
                "step_no": 3,
                "title": "Submit Form",
                "summary": "Submit the completed form for the current row.",
                "role": "RPA Bot",
                "system": "RPA Challenge Platform",
                "input": "Populated form",
                "output": "Form submission confirmation",
            },
        ],
        "roles": ["RPA User", "RPA Bot"],
        "systems": ["RPA Challenge Platform"],
        "operational_facts": {
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
        },
    }

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    rendered_text = str(doc)
    assert "complaint" not in rendered_text.lower()
    assert doc["document_control"]["department"] == "Needs Review"
    assert doc["custom_sop_summary"]["inputs"] == [
        "RPA Challenge web page",
        "Downloaded Excel spreadsheet",
        "Active web form",
        "Excel data row and field mapping",
        "Populated web form",
        "Remaining Excel data",
        "Challenge completion event",
    ]
    assert doc["custom_sop_summary"]["outputs"] == [
        "Downloaded Excel spreadsheet",
        "Challenge timer starts",
        "Field mapping for current round",
        "Populated web form",
        "Form submission confirmation",
        "All items submitted",
        "Completion time result",
    ]


def test_generate_document_from_extraction_expands_rpa_challenge_steps_and_aligns_media():
    extraction = {
        "process_name": "RPA Challenge Data Entry",
        "process_steps": [
            {
                "step_no": 1,
                "title": "Download Input Spreadsheet",
                "summary": "Download the spreadsheet and start the challenge.",
                "role": "Automation Bot",
                "system": "rpachallenge.com",
                "input": "RPA Challenge web page",
                "output": "Challenge started",
            },
            {
                "step_no": 2,
                "title": "Populate Dynamic Form",
                "summary": "Read each row, locate the fields, populate the form, and submit for all 10 rounds.",
                "role": "Automation Bot",
                "system": "rpachallenge.com",
                "input": "Downloaded Excel spreadsheet",
                "output": "Completed challenge",
            },
        ],
        "roles": ["Automation Bot"],
        "systems": ["rpachallenge.com"],
        "operational_facts": {
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
        },
    }
    frames = [
        {"timestamp_seconds": 0, "path": "frame-1.jpg", "reason": "baseline"},
        {"timestamp_seconds": 12, "path": "frame-2.jpg", "reason": "baseline"},
        {"timestamp_seconds": 24, "path": "frame-3.jpg", "reason": "baseline"},
        {"timestamp_seconds": 44.26, "path": "frame-4.jpg", "reason": "process_hotspot"},
        {"timestamp_seconds": 60, "path": "frame-5.jpg", "reason": "baseline"},
        {"timestamp_seconds": 72, "path": "frame-6.jpg", "reason": "baseline"},
        {"timestamp_seconds": 88.03, "path": "frame-7.jpg", "reason": "end_state"},
    ]

    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=frames)
    step_titles = [step["title"] for step in doc["steps"]]
    assert step_titles == [
        "Download Input Spreadsheet",
        "Start Challenge",
        "Identify Field Positions",
        "Input Data into Form",
        "Submit Form",
        "Repeat for All Items",
        "Capture Completion Time",
    ]
    assert [step["source_timestamp"] for step in doc["steps"]] == [
        "00:00:00",
        "00:00:12",
        "00:00:24",
        "00:00:44",
        "00:01:00",
        "00:01:12",
        "00:01:28",
    ]


def test_quality_checks_flag_lost_operational_facts():
    document = {
        "document_control": {"sop_title": "Complaint Intake SOP"},
        "quality_checks": {"checks": []},
        "steps": [{"title": "Receive complaint"}],
        "prerequisites_and_inputs": {"input_documents_data": [{"frequency": "Needs Review"}]},
        "sla_and_performance_targets": [{"kpi": "SLA", "target": "Needs Review"}],
        "tools_and_systems_reference": [{"tool_system": "CRM"}],
    }
    result = run_quality_checks(
        pdd=document,
        sipoc=[{"supplier": "Customer", "input": "Complaint", "process_step": "Receive", "output": "Case", "customer": "Analyst"}],
        confidence=0.8,
        document_type="custom_sop",
        source_facts={"sla_targets": ["Within 24 hours"], "volumes_or_frequency": ["180 to 220 per day"], "systems": ["CRM", "ERP"]},
    )
    flag_types = [flag["type"] for flag in result["flags"]]
    assert "lost_operational_facts" in flag_types
    assert "lost_system_context" in flag_types


def test_quality_checks_flag_missing_pain_points_and_effort_data():
    document = {
        "document_control": {"sop_title": "Complaint Intake SOP"},
        "quality_checks": {"checks": []},
        "steps": [{"title": "Receive complaint"}],
        "prerequisites_and_inputs": {"input_documents_data": [{"frequency": "Daily"}]},
        "sla_and_performance_targets": [{"kpi": "SLA", "target": "Within 24 hours"}],
        "tools_and_systems_reference": [{"tool_system": "CRM"}],
        "automation_opportunities": [],
    }
    result = run_quality_checks(
        pdd=document,
        sipoc=[{"supplier": "Customer", "input": "Complaint", "process_step": "Receive", "output": "Case", "customer": "Analyst"}],
        confidence=0.8,
        document_type="custom_sop",
        source_facts={
            "sla_targets": ["Within 24 hours"],
            "volumes_or_frequency": ["180 to 220 per day"],
            "systems": ["CRM"],
            "pain_points": [{"description": "Manual rework", "quantification": "20 percent", "automation_signal": "high"}],
            "effort_data": [{"step_no": 1, "effort_minutes_min": 8, "effort_minutes_max": 10}],
        },
    )
    messages = [flag["message"] for flag in result["flags"]]
    assert any("pain points" in message for message in messages)
    assert any("effort data" in message for message in messages)
