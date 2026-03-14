import time
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app


def create_authenticated_client() -> TestClient:
    client = TestClient(app)
    auth = client.post("/api/auth/session", json={"code": "PFCD-GUEST-3184"})
    assert auth.status_code == 200
    assert auth.json()["data"]["session"]["role"] == "guest"
    return client


def test_auth_required_for_job_endpoints():
    client = TestClient(app)
    response = client.get("/api/jobs")
    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["error"]["code"] == "ERR_AUTH_REQUIRED"


def test_owner_session_has_no_expiry():
    client = TestClient(app)
    auth = client.post("/api/auth/session", json={"code": "PFCD-OWNER-7429"})
    assert auth.status_code == 200
    payload = auth.json()["data"]["session"]
    assert payload["role"] == "owner"
    assert payload["expires_at"] is None


def test_end_to_end_job_review_finalize_export_flow(tmp_path: Path):
    client = create_authenticated_client()

    transcript_path = tmp_path / "flow.txt"
    transcript_path.write_text(
        "Customer submits request\nAnalyst validates request\nSystem updates ticket\n",
        encoding="utf-8",
    )

    with transcript_path.open("rb") as f:
        create = client.post(
            "/api/jobs",
            files={"transcript_file": ("flow.txt", f, "text/plain")},
            data={"provider": "google", "processing_profile": "balanced"},
        )
    assert create.status_code == 202
    payload = create.json()
    assert payload["success"] is True
    job_id = payload["data"]["job_id"]

    # Wait briefly for background task completion.
    for _ in range(15):
        job = client.get(f"/api/jobs/{job_id}")
        assert job.status_code == 200
        state = job.json()["data"]["status"]
        if state in {"needs_review", "failed", "completed"}:
            break
        time.sleep(0.2)

    assert state == "needs_review"

    draft = client.get(f"/api/jobs/{job_id}/draft")
    assert draft.status_code == 200
    draft_payload = draft.json()["data"]
    assert draft_payload["document_type"] == "pdd"
    assert isinstance(draft_payload["document"], dict)
    assert isinstance(draft_payload["sipoc"], list)
    assert isinstance(draft_payload["document_markdown"], str)
    assert "## 1. Document Control" in draft_payload["document_markdown"]

    # Save same draft back (schema validation path).
    save = client.put(
        f"/api/jobs/{job_id}/draft",
        json={
            "document_type": draft_payload["document_type"],
            "document": draft_payload["document"],
            "sipoc": draft_payload["sipoc"],
        },
    )
    assert save.status_code == 200
    assert save.json()["success"] is True

    finalize = client.post(f"/api/jobs/{job_id}/finalize")
    assert finalize.status_code == 202
    assert finalize.json()["data"]["status"] == "completed"

    job_after_finalize = client.get(f"/api/jobs/{job_id}")
    assert job_after_finalize.status_code == 200
    expires_at = datetime.fromisoformat(job_after_finalize.json()["data"]["expires_at"])
    assert expires_at > datetime.utcnow() + timedelta(days=6)

    finalize_again = client.post(f"/api/jobs/{job_id}/finalize")
    assert finalize_again.status_code == 200
    assert finalize_again.json()["data"]["status"] == "completed"
    assert finalize_again.json()["data"]["idempotent"] is True

    md = client.get(f"/api/jobs/{job_id}/exports/md")
    js = client.get(f"/api/jobs/{job_id}/exports/json")
    pdf = client.get(f"/api/jobs/{job_id}/exports/pdf")
    docx = client.get(f"/api/jobs/{job_id}/exports/docx")
    assert md.status_code == 200
    assert js.status_code == 200
    assert pdf.status_code == 200
    assert docx.status_code == 200
    assert len(md.content) > 0
    assert len(js.content) > 0
    assert len(pdf.content) > 0
    assert len(docx.content) > 0


def test_list_jobs_endpoint_returns_recent_jobs(tmp_path: Path):
    client = create_authenticated_client()

    transcript_path = tmp_path / "list-flow.txt"
    transcript_path.write_text("Start\nValidate\nComplete\n", encoding="utf-8")
    with transcript_path.open("rb") as f:
        create = client.post(
            "/api/jobs",
            files={"transcript_file": ("list-flow.txt", f, "text/plain")},
            data={"provider": "google", "processing_profile": "balanced"},
        )
    assert create.status_code == 202
    job_id = create.json()["data"]["job_id"]

    listing = client.get("/api/jobs?limit=20")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["success"] is True
    jobs = payload["data"]["jobs"]
    assert isinstance(jobs, list)
    assert any(row["id"] == job_id for row in jobs)


def test_sop_finalize_requires_complete_sop_contract(tmp_path: Path):
    client = create_authenticated_client()
    transcript_path = tmp_path / "sop-flow.txt"
    transcript_path.write_text("Start\nValidate\nComplete\n", encoding="utf-8")
    with transcript_path.open("rb") as f:
        create = client.post(
            "/api/jobs",
            files={"transcript_file": ("sop-flow.txt", f, "text/plain")},
            data={"provider": "google", "processing_profile": "balanced", "document_template": "sop"},
        )
    assert create.status_code == 202
    job_id = create.json()["data"]["job_id"]

    for _ in range(15):
        job = client.get(f"/api/jobs/{job_id}")
        state = job.json()["data"]["status"]
        if state in {"needs_review", "failed", "completed"}:
            break
        time.sleep(0.2)
    assert state == "needs_review"

    draft = client.get(f"/api/jobs/{job_id}/draft").json()["data"]
    assert draft["document_type"] == "sop"

    # Remove required SOP section to force finalize validation failure.
    bad_document = dict(draft["document"])
    bad_document["quality_checks"] = {}
    save = client.put(
        f"/api/jobs/{job_id}/draft",
        json={"document_type": "sop", "document": bad_document, "sipoc": draft["sipoc"]},
    )
    assert save.status_code == 200
    finalize = client.post(f"/api/jobs/{job_id}/finalize")
    assert finalize.status_code == 409
    assert finalize.json()["success"] is False


def test_custom_sop_uses_custom_template_and_finalize_contract(tmp_path: Path):
    client = create_authenticated_client()
    transcript_path = tmp_path / "custom-sop-flow.txt"
    transcript_path.write_text("Start\nValidate\nComplete\n", encoding="utf-8")
    with transcript_path.open("rb") as f:
        create = client.post(
            "/api/jobs",
            files={"transcript_file": ("custom-sop-flow.txt", f, "text/plain")},
            data={"provider": "google", "processing_profile": "balanced", "document_template": "custom_sop"},
        )
    assert create.status_code == 202
    job_id = create.json()["data"]["job_id"]

    for _ in range(15):
        job = client.get(f"/api/jobs/{job_id}")
        state = job.json()["data"]["status"]
        if state in {"needs_review", "failed", "completed"}:
            break
        time.sleep(0.2)
    assert state == "needs_review"

    draft_response = client.get(f"/api/jobs/{job_id}/draft")
    assert draft_response.status_code == 200
    draft = draft_response.json()["data"]
    assert draft["document_type"] == "custom_sop"
    assert "## Index" in draft["document_markdown"]

    bad_document = dict(draft["document"])
    bad_document["quality_checks"] = {}
    save = client.put(
        f"/api/jobs/{job_id}/draft",
        json={"document_type": "custom_sop", "document": bad_document, "sipoc": draft["sipoc"]},
    )
    assert save.status_code == 200
    finalize = client.post(f"/api/jobs/{job_id}/finalize")
    assert finalize.status_code == 409
    assert finalize.json()["success"] is False


def test_custom_sop_pdf_export_contains_custom_template_markers(tmp_path: Path):
    client = create_authenticated_client()
    transcript_path = tmp_path / "custom-sop-export.txt"
    transcript_path.write_text("Start\nValidate\nComplete\n", encoding="utf-8")
    with transcript_path.open("rb") as f:
        create = client.post(
            "/api/jobs",
            files={"transcript_file": ("custom-sop-export.txt", f, "text/plain")},
            data={"provider": "google", "processing_profile": "balanced", "document_template": "custom_sop"},
        )
    assert create.status_code == 202
    job_id = create.json()["data"]["job_id"]

    for _ in range(20):
        job = client.get(f"/api/jobs/{job_id}")
        state = job.json()["data"]["status"]
        if state in {"needs_review", "failed", "completed"}:
            break
        time.sleep(0.2)
    assert state == "needs_review"

    finalize = client.post(f"/api/jobs/{job_id}/finalize")
    assert finalize.status_code == 202

    pdf = client.get(f"/api/jobs/{job_id}/exports/pdf")
    assert pdf.status_code == 200
    extracted = "\n".join((page.extract_text() or "") for page in PdfReader(BytesIO(pdf.content)).pages)
    assert "Standard Operating Procedure (SOP)" in extracted
    assert "SOP Template" not in extracted
    assert "Index" in extracted
    assert "Notes for AI Usage" not in extracted
