import json
from html import escape
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from docx import Document
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.pdd_template import render_standard_pdd_markdown


def _render_markdown(pdd: Dict, sipoc: List[Dict]) -> str:
    return render_standard_pdd_markdown(pdd=pdd, sipoc=sipoc)


def _render_pdf_from_docx(docx_path: Path, target_path: Path) -> None:
    styles = getSampleStyleSheet()
    heading_1 = ParagraphStyle("DocxHeading1", parent=styles["Heading1"], fontSize=16, leading=20, spaceAfter=6)
    heading_2 = ParagraphStyle("DocxHeading2", parent=styles["Heading2"], fontSize=13, leading=17, spaceBefore=6, spaceAfter=4)
    heading_3 = ParagraphStyle("DocxHeading3", parent=styles["Heading3"], fontSize=11, leading=14, spaceBefore=4, spaceAfter=2)
    body = ParagraphStyle("DocxBody", parent=styles["BodyText"], fontSize=10, leading=13, spaceAfter=3)
    bullet = ParagraphStyle("DocxBullet", parent=body, leftIndent=12, bulletIndent=4)
    table_cell = ParagraphStyle("DocxTableCell", parent=body, fontSize=8.6, leading=10, spaceAfter=0, wordWrap="CJK")
    table_header = ParagraphStyle("DocxTableHeader", parent=table_cell, fontName="Helvetica-Bold")

    pdf = SimpleDocTemplate(
        str(target_path),
        pagesize=A4,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    story = []

    doc = Document(str(docx_path))
    for block in doc.element.body:
        if block.tag.endswith("}p"):
            paragraph = next((p for p in doc.paragraphs if p._element is block), None)
            text = (paragraph.text if paragraph else "").strip()
            if not text:
                story.append(Spacer(1, 2))
                continue
            style_name = str(getattr(paragraph.style, "name", "") or "")
            if style_name.startswith("Heading 1"):
                story.append(Paragraph(escape(text), heading_1))
            elif style_name.startswith("Heading 2"):
                story.append(Paragraph(escape(text), heading_2))
            elif style_name.startswith("Heading 3"):
                story.append(Paragraph(escape(text), heading_3))
            elif "List Bullet" in style_name:
                story.append(Paragraph(escape(text), bullet, bulletText="•"))
            else:
                story.append(Paragraph(escape(text), body))
            continue

        if block.tag.endswith("}tbl"):
            table = next((t for t in doc.tables if t._element is block), None)
            if not table:
                continue
            table_rows = []
            for row_idx, row in enumerate(table.rows):
                rendered_row = []
                for cell in row.cells:
                    text = escape(cell.text.strip().replace("\n", " "))
                    style = table_header if row_idx == 0 else table_cell
                    rendered_row.append(Paragraph(text or "-", style))
                table_rows.append(rendered_row)
            if not table_rows:
                continue
            col_width = (A4[0] - (24 * mm)) / len(table_rows[0])
            pdf_table = Table(table_rows, repeatRows=1, colWidths=[col_width] * len(table_rows[0]))
            pdf_table.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("FONTSIZE", (0, 0), (-1, -1), 8.8),
                        ("LEADING", (0, 0), (-1, -1), 10),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            story.append(pdf_table)
            story.append(Spacer(1, 6))

    if not story:
        story.append(Paragraph("No content available for PDF export.", body))
    pdf.build(story)


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


def _safe_name_token(raw: str) -> str:
    chars = []
    for ch in (raw or "").strip().lower():
        if ch.isalnum():
            chars.append(ch)
        elif ch in {" ", "-", "_"}:
            chars.append("_")
    token = "".join(chars).strip("_")
    while "__" in token:
        token = token.replace("__", "_")
    return token[:80] or "process"


def _resolve_process_name(pdd: Dict, provided_name: Optional[str]) -> str:
    if provided_name and provided_name.strip():
        return provided_name.strip()
    steps = pdd.get("steps", []) if isinstance(pdd.get("steps"), list) else []
    if steps and str(steps[0].get("title", "")).strip():
        return str(steps[0]["title"]).strip()
    return "process"


def generate_exports(
    job_id: str,
    pdd: Dict,
    sipoc: List[Dict],
    exports_root: Path,
    process_name: Optional[str] = None,
    llm_provider: Optional[str] = None,
    processed_at: Optional[datetime] = None,
) -> Dict:
    job_dir = exports_root / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    processed_at = processed_at or datetime.utcnow()
    process_token = _safe_name_token(_resolve_process_name(pdd, process_name))
    provider_token = _safe_name_token(llm_provider or "provider")
    date_token = processed_at.strftime("%Y%m%d")
    base_name = f"{process_token}_processed_{date_token}_{provider_token}"

    md_content = _render_markdown(pdd, sipoc)
    md_path = job_dir / f"{base_name}.md"
    json_path = job_dir / f"{base_name}.json"
    pdf_path = job_dir / f"{base_name}.pdf"
    docx_path = job_dir / f"{base_name}.docx"

    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json.dumps({"pdd": pdd, "sipoc": sipoc}, indent=2), encoding="utf-8")
    _render_docx(pdd, sipoc, docx_path)
    _render_pdf_from_docx(docx_path, pdf_path)

    return {"md": str(md_path), "json": str(json_path), "pdf": str(pdf_path), "docx": str(docx_path)}
