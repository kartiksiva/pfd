import json
import re
import base64
from pathlib import Path
from typing import Any, Dict, Optional

import httpx


PROMPT_TEMPLATE = """
You are a business process analyst.
Extract a Process Definition and SIPOC from the source transcript.
Return ONLY valid JSON with this schema:
{
  "process_name": "string",
  "purpose": "string",
  "scope": "string",
  "triggers": ["string"],
  "preconditions": ["string"],
  "process_steps": [
    {
      "step_no": 1,
      "title": "short action title",
      "summary": "what happens in this step",
      "role": "actor role",
      "system": "system/application",
      "input": "primary input",
      "output": "primary output",
      "exception": "optional exception"
    }
  ],
  "roles": ["string"],
  "systems": ["string"],
  "business_rules": ["string"],
  "decision_rules": [
    {
      "condition": "string",
      "action": "string",
      "applies_to_step": 1
    }
  ],
  "exceptions": ["string"],
  "outputs": ["string"],
  "metrics": ["string"],
  "risks": ["string"],
  "effort_data": [
    {
      "step_no": 1,
      "effort_minutes_min": 0,
      "effort_minutes_max": 0
    }
  ],
  "pain_points": [
    {
      "description": "string",
      "quantification": "string",
      "automation_signal": "high|medium|low"
    }
  ],
  "operational_facts": {
    "frequency": "string",
    "volumes_or_frequency": ["string"],
    "sla_targets": ["string"],
    "routing_rules": ["string"],
    "control_requirements": ["string"],
    "governance_notes": ["string"],
    "quantified_pain_points": ["string"],
    "systems": ["string"],
    "teams": ["string"],
    "exception_details": ["string"]
  },
  "sipoc": [
    {
      "supplier": "string",
      "input": "string",
      "process_step": "string",
      "output": "string",
      "customer": "string"
    }
  ],
  "confidence": 0.0
}

Rules:
- Consolidate transcript noise into business-ready steps.
- Remove timestamps/speaker labels from step action text.
- Include approvals, SLAs, exception paths, controls, and completion criteria where present.
- Extract any stated effort times, volumes, error rates, and SLA commitments as structured data fields, not narrative-only text.
- Extract the current-state process only; do not mix future-state recommendations into steps, exceptions, controls, or governance facts.
- Do not copy facilitator questions or workshop quotes verbatim into structured fields when a concise paraphrase is possible.
- Do not invent approvers, contact details, or ownership that are not supported by the transcript.
- Keep confidence between 0.0 and 1.0.

__TRANSCRIPT__
""".strip()


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_operational_facts(payload: Dict[str, Any]) -> Dict[str, Any]:
    facts = payload.get("operational_facts", {})
    if not isinstance(facts, dict):
        facts = {}
    return {
        "frequency": str(facts.get("frequency", "")).strip(),
        "volumes_or_frequency": _as_list(facts.get("volumes_or_frequency")),
        "sla_targets": _as_list(facts.get("sla_targets")),
        "routing_rules": _as_list(facts.get("routing_rules")),
        "control_requirements": _as_list(facts.get("control_requirements")),
        "governance_notes": _as_list(facts.get("governance_notes")),
        "quantified_pain_points": _as_list(facts.get("quantified_pain_points")),
        "systems": _as_list(facts.get("systems")),
        "teams": _as_list(facts.get("teams")),
        "exception_details": _as_list(facts.get("exception_details")),
    }


def _normalize_effort_data(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    rows = payload.get("effort_data", [])
    normalized = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            step_no = _as_int(row.get("step_no"), 0)
            effort_min = _as_int(row.get("effort_minutes_min"), 0)
            effort_max = _as_int(row.get("effort_minutes_max"), 0)
            if step_no <= 0 or effort_min <= 0 or effort_max <= 0:
                continue
            normalized.append(
                {
                    "step_no": step_no,
                    "effort_minutes_min": min(effort_min, effort_max),
                    "effort_minutes_max": max(effort_min, effort_max),
                }
            )
    return normalized


def _normalize_decision_rules(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    rows = payload.get("decision_rules", [])
    normalized = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            condition = str(row.get("condition", "")).strip()
            action = str(row.get("action", "")).strip()
            applies_to_step = _as_int(row.get("applies_to_step"), 0)
            if not condition or not action:
                continue
            normalized.append(
                {
                    "condition": condition,
                    "action": action,
                    "applies_to_step": applies_to_step if applies_to_step > 0 else None,
                }
            )
    return normalized


def _normalize_pain_points(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    rows = payload.get("pain_points", [])
    normalized = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            description = str(row.get("description", "")).strip()
            quantification = str(row.get("quantification", "")).strip()
            automation_signal = str(row.get("automation_signal", "")).strip().lower()
            if not description:
                continue
            if automation_signal not in {"high", "medium", "low"}:
                automation_signal = "medium"
            normalized.append(
                {
                    "description": description,
                    "quantification": quantification,
                    "automation_signal": automation_signal,
                }
            )
    return normalized


def _normalize_extraction(payload: Dict[str, Any]) -> Dict[str, Any]:
    steps_in = payload.get("process_steps", [])
    normalized_steps = []
    if isinstance(steps_in, list):
        for idx, step in enumerate(steps_in, start=1):
            if not isinstance(step, dict):
                continue
            summary = str(step.get("summary", "")).strip()
            title = str(step.get("title", "")).strip() or (summary[:80] if summary else f"Step {idx}")
            normalized_steps.append(
                {
                    "step_no": int(step.get("step_no") or idx),
                    "title": title,
                    "summary": summary,
                    "role": str(step.get("role", "operator")).strip() or "operator",
                    "system": str(step.get("system", "manual_or_unspecified")).strip() or "manual_or_unspecified",
                    "input": str(step.get("input", "process input")).strip() or "process input",
                    "output": str(step.get("output", summary)).strip() or summary,
                    "exception": str(step.get("exception", "")).strip(),
                }
            )
    normalized_steps = sorted(normalized_steps, key=lambda s: s["step_no"])

    sipoc_in = payload.get("sipoc", [])
    sipoc = []
    if isinstance(sipoc_in, list):
        for row in sipoc_in:
            if not isinstance(row, dict):
                continue
            supplier = str(row.get("supplier", "")).strip()
            input_ = str(row.get("input", "")).strip()
            process_step = str(row.get("process_step", "")).strip()
            output = str(row.get("output", "")).strip()
            customer = str(row.get("customer", "")).strip()
            if supplier or input_ or process_step or output or customer:
                sipoc.append(
                    {
                        "supplier": supplier or "upstream_supplier",
                        "input": input_ or "process input",
                        "process_step": process_step or "unspecified",
                        "output": output or "unspecified",
                        "customer": customer or "downstream_customer",
                    }
                )

    confidence_raw = payload.get("confidence", 0.7)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.7
    confidence = max(0.0, min(1.0, confidence))

    return {
        "process_name": str(payload.get("process_name", "")).strip() or "Analyzed Process",
        "purpose": str(payload.get("purpose", "")).strip() or "Document current process flow from submitted evidence.",
        "scope": str(payload.get("scope", "")).strip() or "Current-state process only.",
        "triggers": _as_list(payload.get("triggers")),
        "preconditions": _as_list(payload.get("preconditions")),
        "process_steps": normalized_steps,
        "roles": _as_list(payload.get("roles")),
        "systems": _as_list(payload.get("systems")),
        "business_rules": _as_list(payload.get("business_rules")),
        "decision_rules": _normalize_decision_rules(payload),
        "exceptions": _as_list(payload.get("exceptions")),
        "outputs": _as_list(payload.get("outputs")),
        "metrics": _as_list(payload.get("metrics")),
        "risks": _as_list(payload.get("risks")),
        "effort_data": _normalize_effort_data(payload),
        "pain_points": _normalize_pain_points(payload),
        "operational_facts": _normalize_operational_facts(payload),
        "sipoc": sipoc,
        "confidence": confidence,
    }


def _compose_prompt_text(transcript_text: str, context_notes: Optional[str]) -> str:
    transcript_block = transcript_text[:120000] if transcript_text else "No transcript provided."
    if context_notes and str(context_notes).strip():
        return (
            "Additional context provided by user:\n"
            f"{str(context_notes).strip()[:2000]}\n\n"
            "Source transcript:\n"
            f"{transcript_block}"
        )
    return f"Source transcript:\n{transcript_block}"


def _frame_context_lines(frame_images: list[dict[str, Any]]) -> str:
    if not frame_images:
        return ""
    lines = ["Frame evidence timestamps and reasons:"]
    for frame in frame_images[:20]:
        lines.append(
            f"- {float(frame.get('timestamp_seconds', 0.0)):.2f}s | {str(frame.get('reason', 'frame'))}"
        )
    return "\n".join(lines)


def _google_extract(
    transcript_text: str,
    api_key: str,
    model: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", _compose_prompt_text(transcript_text, context_notes))
    frame_ctx = _frame_context_lines(frame_images)
    if frame_ctx:
        prompt = f"{prompt}\n\n{frame_ctx}"
    parts = [{"text": prompt}]
    for frame in frame_images[:8]:
        frame_path = Path(str(frame.get("path") or ""))
        if not frame_path.exists():
            continue
        parts.append(
            {
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": base64.b64encode(frame_path.read_bytes()).decode("ascii"),
                }
            }
        )
    body = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, json=body)
        response.raise_for_status()
        data = response.json()
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    parsed = _extract_json(text)
    return _normalize_extraction(parsed) if parsed else None


def _openai_extract(
    transcript_text: str,
    api_key: str,
    model: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", _compose_prompt_text(transcript_text, context_notes))
    frame_ctx = _frame_context_lines(frame_images)
    if frame_ctx:
        prompt = f"{prompt}\n\n{frame_ctx}"
    content = [{"type": "text", "text": prompt}]
    for frame in frame_images[:8]:
        frame_path = Path(str(frame.get("path") or ""))
        if not frame_path.exists():
            continue
        b64 = base64.b64encode(frame_path.read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You extract business process structure and return strict JSON only."},
            {"role": "user", "content": content},
        ],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = _extract_json(text)
    return _normalize_extraction(parsed) if parsed else None


def _azure_openai_extract(
    transcript_text: str,
    api_key: str,
    deployment: str,
    endpoint: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    base = endpoint.rstrip("/")
    # Azure OpenAI OpenAI-compatible v1 format.
    url = f"{base}/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", _compose_prompt_text(transcript_text, context_notes))
    frame_ctx = _frame_context_lines(frame_images)
    if frame_ctx:
        prompt = f"{prompt}\n\n{frame_ctx}"
    content = [{"type": "text", "text": prompt}]
    for frame in frame_images[:8]:
        frame_path = Path(str(frame.get("path") or ""))
        if not frame_path.exists():
            continue
        b64 = base64.b64encode(frame_path.read_bytes()).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    body = {
        "model": deployment,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You extract business process structure and return strict JSON only."},
            {"role": "user", "content": content},
        ],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = _extract_json(text)
    return _normalize_extraction(parsed) if parsed else None


def _ollama_extract(
    transcript_text: str,
    model: str,
    base_url: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/generate"
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", _compose_prompt_text(transcript_text, context_notes))
    frame_ctx = _frame_context_lines(frame_images)
    if frame_ctx:
        prompt = f"{prompt}\n\n{frame_ctx}"
    images = []
    for frame in frame_images[:8]:
        frame_path = Path(str(frame.get("path") or ""))
        if not frame_path.exists():
            continue
        images.append(base64.b64encode(frame_path.read_bytes()).decode("ascii"))
    body = {
        "model": model,
        "prompt": prompt,
        "images": images,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, json=body)
        response.raise_for_status()
        data = response.json()
    text = data.get("response", "")
    parsed = _extract_json(text)
    return _normalize_extraction(parsed) if parsed else None


def extract_with_llm(
    provider: str,
    transcript_text: str,
    context_notes: Optional[str],
    api_key: Optional[str],
    model: str,
    ollama_base_url: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    frame_images: Optional[list[dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    frame_images = frame_images or []
    if (not transcript_text and not frame_images) or not api_key:
        if provider != "ollama":
            return None
    try:
        if provider == "google":
            return _google_extract(transcript_text=transcript_text, context_notes=context_notes, api_key=api_key, model=model, frame_images=frame_images)
        if provider == "azure_openai":
            if not azure_endpoint:
                return None
            return _azure_openai_extract(
                transcript_text=transcript_text,
                context_notes=context_notes,
                api_key=api_key,
                deployment=model,
                endpoint=azure_endpoint,
                frame_images=frame_images,
            )
        if provider == "ollama":
            return _ollama_extract(
                transcript_text=transcript_text,
                context_notes=context_notes,
                model=model,
                base_url=ollama_base_url or "http://127.0.0.1:11434",
                frame_images=frame_images,
            )
        return _openai_extract(transcript_text=transcript_text, context_notes=context_notes, api_key=api_key, model=model, frame_images=frame_images)
    except Exception:
        return None
