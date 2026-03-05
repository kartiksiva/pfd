import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_end_to_end_job_review_finalize_export_flow(tmp_path: Path):
    client = TestClient(app)

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
    assert isinstance(draft_payload["pdd"], dict)
    assert isinstance(draft_payload["sipoc"], list)
    assert isinstance(draft_payload["pdd_markdown"], str)
    assert "## 1. Document Control" in draft_payload["pdd_markdown"]

    # Save same draft back (schema validation path).
    save = client.put(
        f"/api/jobs/{job_id}/draft",
        json={"pdd": draft_payload["pdd"], "sipoc": draft_payload["sipoc"]},
    )
    assert save.status_code == 200
    assert save.json()["success"] is True

    finalize = client.post(f"/api/jobs/{job_id}/finalize")
    assert finalize.status_code == 202
    assert finalize.json()["data"]["status"] == "completed"

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
