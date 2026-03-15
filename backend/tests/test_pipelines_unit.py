from app.pipelines.document_generation import PDD_SECTION_ORDER, generate_document_from_extraction, generate_pdd_document, generate_sipoc_rows
from app.pipelines.process_extraction import extract_process_structure
from app.pipelines.quality_checks import run_quality_checks


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


def test_generate_document_from_extraction_avoids_generic_step_title_for_sop_title():
    extraction = _sample_extraction()
    extraction["process_name"] = "Invoice Reconciliation"
    doc = generate_document_from_extraction(extraction, document_type="custom_sop", frame_images=[])
    assert doc["document_control"]["sop_title"] == "Invoice Reconciliation"
