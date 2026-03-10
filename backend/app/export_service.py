import json
from datetime import date
from pathlib import Path
from typing import Dict, List

from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.pdd_template import render_standard_pdd_markdown


def _render_markdown(pdd: Dict, sipoc: List[Dict]) -> str:
    return render_standard_pdd_markdown(pdd=pdd, sipoc=sipoc)


def _render_pdf_from_docx(docx_path: Path, target_path: Path) -> None:
    c = canvas.Canvas(str(target_path), pagesize=A4)
    _, height = A4
    y = height - 40

    doc = Document(str(docx_path))
    for block in doc.element.body:
        if y < 40:
            c.showPage()
            y = height - 40

        if block.tag.endswith("}p"):
            paragraph = next((p for p in doc.paragraphs if p._element is block), None)
            text = (paragraph.text if paragraph else "").strip()
            if not text:
                y -= 8
                continue
            c.drawString(40, y, text[:115])
            y -= 14
            continue

        if block.tag.endswith("}tbl"):
            table = next((t for t in doc.tables if t._element is block), None)
            if not table:
                continue
            y -= 4
            for row in table.rows:
                row_text = " | ".join(cell.text.strip().replace("\n", " ") for cell in row.cells)
                if y < 40:
                    c.showPage()
                    y = height - 40
                c.drawString(40, y, row_text[:115])
                y -= 13
            y -= 6

    c.save()


def _add_labeled_bullet(doc: Document, label: str, value: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.add_run(label).bold = True
    p.add_run(value)


def _add_table(doc: Document, headers: List[str], rows: List[List[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for idx, h in enumerate(headers):
        table.rows[0].cells[idx].text = h
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            cells[idx].text = value


def _render_docx(pdd: Dict, sipoc: List[Dict], target_path: Path) -> None:
    doc = Document()
    steps = pdd.get("steps", []) if isinstance(pdd.get("steps"), list) else []
    systems = pdd.get("systems", []) if isinstance(pdd.get("systems"), list) else []
    business_rules = pdd.get("business_rules", []) if isinstance(pdd.get("business_rules"), list) else []
    exceptions = pdd.get("exceptions", []) if isinstance(pdd.get("exceptions"), list) else []
    preconditions = pdd.get("preconditions", []) if isinstance(pdd.get("preconditions"), list) else []
    metrics = pdd.get("metrics", []) if isinstance(pdd.get("metrics"), list) else []
    risks = pdd.get("risks", []) if isinstance(pdd.get("risks"), list) else []
    triggers = pdd.get("triggers", []) if isinstance(pdd.get("triggers"), list) else []
    outputs = pdd.get("outputs", []) if isinstance(pdd.get("outputs"), list) else []

    process_name = (steps[0].get("title", "") if steps else "").strip() or "Analyzed Process"
    purpose = str(pdd.get("purpose", "")).strip() or "Document current process flow from submitted evidence."
    scope = str(pdd.get("scope", "")).strip() or "Current-state process only."

    doc.add_heading(f"{process_name} - Process Definition Document (PDD)", level=1)

    doc.add_heading("1. Document Control", level=2)
    _add_table(
        doc,
        ["Version", "Date", "Author", "Description"],
        [["1.0", date.today().isoformat(), "PFCD Agent", "Initial Draft (As-Is Process)"]],
    )

    doc.add_heading("2. Process Overview", level=2)
    _add_labeled_bullet(doc, "Process Name: ", process_name)
    _add_labeled_bullet(doc, "Objective: ", purpose)
    _add_labeled_bullet(doc, "Frequency: ", triggers[0] if triggers else "TBD")
    _add_labeled_bullet(doc, "Estimated Volume: ", "TBD")
    _add_labeled_bullet(doc, "Manual Effort: ", "TBD")

    doc.add_heading("3. Scope", level=2)
    doc.add_heading("3.1 In-Scope", level=3)
    doc.add_paragraph(scope, style="List Bullet")
    doc.add_heading("3.2 Out-of-Scope", level=3)
    doc.add_paragraph("Future-state redesign and optimization.", style="List Bullet")

    doc.add_heading("4. Prerequisites & Systems", level=2)
    doc.add_heading("4.1 Prerequisites", level=3)
    if preconditions:
        for item in preconditions:
            doc.add_paragraph(str(item), style="List Bullet")
    else:
        doc.add_paragraph("None explicitly stated in source evidence.", style="List Bullet")
    doc.add_heading("4.2 Application Inventory", level=3)
    _add_table(
        doc,
        ["Application", "Version", "Access Method"],
        [[str(app), "Unknown", "As observed in evidence"] for app in systems] or [["Unspecified", "Unknown", "Unknown"]],
    )

    doc.add_heading("5. Detailed Process Steps (As-Is)", level=2)
    _add_table(
        doc,
        ["Step #", "Action", "Role", "System", "Input", "Output"],
        [
            [
                str(step.get("step_no", "")),
                str(step.get("description", "") or step.get("title", "")),
                str(step.get("actor", "")),
                str(step.get("system", "")),
                str(step.get("input", "")),
                str(step.get("output", "")),
            ]
            for step in steps
        ]
        or [["1.1", "Step details unavailable", "Unspecified", "Unspecified", "Unspecified", "Unspecified"]],
    )

    doc.add_heading("6. Business Rules & Logic", level=2)
    if business_rules:
        for idx, rule in enumerate(business_rules, start=1):
            _add_labeled_bullet(doc, f"Rule {idx}: ", str(rule))
    else:
        doc.add_paragraph("No explicit business rules identified from source evidence.", style="List Bullet")

    doc.add_heading("7. Exceptions Handling", level=2)
    doc.add_heading("7.1 Business Exceptions", level=3)
    if exceptions:
        for exc in exceptions:
            doc.add_paragraph(str(exc), style="List Bullet")
    else:
        doc.add_paragraph("None captured.", style="List Bullet")
    doc.add_heading("7.2 Technical Exceptions", level=3)
    doc.add_paragraph("Retry, log, and escalate to technical owner if persistent.", style="List Bullet")

    doc.add_heading("8. Inputs & Outputs", level=2)
    _add_labeled_bullet(doc, "Primary Input: ", sipoc[0].get("input", "Unspecified") if sipoc else "Unspecified")
    _add_labeled_bullet(doc, "Primary Output: ", outputs[0] if outputs else (sipoc[-1].get("output", "Unspecified") if sipoc else "Unspecified"))

    doc.add_heading("9. Metrics & Risks", level=2)
    if metrics:
        for metric in metrics:
            _add_labeled_bullet(doc, "Success Metric: ", str(metric))
    else:
        _add_labeled_bullet(doc, "Success Metric: ", "Not explicitly defined.")
    if risks:
        for risk in risks:
            _add_labeled_bullet(doc, "Risk: ", str(risk))
            _add_labeled_bullet(doc, "Mitigation: ", "Define owner, threshold, and contingency action.")
    else:
        _add_labeled_bullet(doc, "Risk: ", "No explicit risks identified.")

    doc.add_heading("10. SIPOC", level=2)
    _add_table(
        doc,
        ["Supplier", "Input", "Process", "Output", "Customer"],
        [
            [
                str(row.get("supplier", "")),
                str(row.get("input", "")),
                str(row.get("process_step", "")),
                str(row.get("output", "")),
                str(row.get("customer", "")),
            ]
            for row in sipoc
        ]
        or [["upstream_supplier", "process input", "unspecified", "unspecified", "downstream_customer"]],
    )

    doc.add_paragraph("Document generated for Process Excellence / Automation Readiness.")
    doc.save(str(target_path))


def generate_exports(job_id: str, pdd: Dict, sipoc: List[Dict], exports_root: Path) -> Dict:
    job_dir = exports_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    md_content = _render_markdown(pdd, sipoc)
    md_path = job_dir / "report.md"
    json_path = job_dir / "report.json"
    pdf_path = job_dir / "report.pdf"
    docx_path = job_dir / "report.docx"

    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json.dumps({"pdd": pdd, "sipoc": sipoc}, indent=2), encoding="utf-8")
    _render_docx(pdd, sipoc, docx_path)
    _render_pdf_from_docx(docx_path, pdf_path)

    return {"md": str(md_path), "json": str(json_path), "pdf": str(pdf_path), "docx": str(docx_path)}
