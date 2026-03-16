import json
import logging
import re
import base64
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

MAX_EXTRACTION_OUTPUT_TOKENS = 4096
MAX_EXTRACTION_RETRIES = 2
MAX_RAW_PREVIEW_CHARS = 1000
SYSTEM_PROMPT = """
You are a business process analyst specialising in current-state process documentation.

Extraction policy - always apply:
- Return valid JSON only. No markdown fences, no preamble, no trailing commentary.
- Extract the current-state process only. Never include future-state recommendations,
  proposed automation, improvement suggestions, or hypothetical redesigns in any field.
- Do not invent roles, system names, approvers, owners, or contact details that are
  not directly supported by the transcript or frame evidence.
- Prefer concise paraphrase over verbatim transcript quotes. Remove speaker labels,
  timestamps, and turn markers from all extracted text fields.
- Preserve evidence-backed operational facts as structured fields, not narrative prose:
  SLA targets, volume ranges, error rates, effort times, exception scenarios,
  routing rules, and compliance requirements all belong in structured fields.
- Facilitator questions, workshop prompts, and hypothetical future-state statements
  must never appear in process_steps, exceptions, business_rules, or operational_facts.
- Confidence must reflect actual evidence strength. A sparse or ambiguous transcript
  warrants confidence <= 0.55. Do not exceed 0.85 unless steps, roles, and systems
  are all explicitly named and sequenced in the evidence.
""".strip()

_TEMPLATE_HINTS = {
    "pdd": (
        "Document template: PDD (Process Definition Document).\n"
        "Emphasise: process_steps sequence, roles, systems, and SIPOC coverage.\n"
        "Capture every discrete action visible in the evidence, including short steps such as "
        "'open application' or 'download file' if they appear.\n"
        "Do not emphasise exception matrices, training requirements, or controls beyond "
        "what is directly stated in the evidence."
    ),
    "sop": (
        "Document template: SOP (Standard Operating Procedure).\n"
        "Emphasise: exception_details, control_requirements, sla_targets, governance_notes, "
        "and any training or knowledge-transfer references in operational_facts.\n"
        "For each exception extract: the scenario, the trigger condition, and the resolution action.\n"
        "Do not invent quality-check steps, approval paths, or escalation contacts not "
        "present in the evidence."
    ),
    "custom_sop": (
        "Document template: Custom SOP.\n"
        "Same emphasis as SOP. Additionally: populate pain_points with quantification and "
        "automation_signal. Where effort times are mentioned, populate effort_data per step.\n"
        "Set automation_signal to 'high' only when the transcript explicitly states volume, "
        "repetition, or rule-based manual work. Do not infer automation potential from "
        "general process descriptions alone."
    ),
}

PROMPT_TEMPLATE = """
Extract a Process Definition and SIPOC from the source transcript below.
Return ONLY valid JSON matching this schema exactly:
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
      "summary": "what happens - current state only",
      "role": "actor role",
      "system": "system or application used",
      "input": "primary input",
      "output": "primary output",
      "exception": "exception or empty string"
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

Counter-example - do NOT produce this:
  business_rules: ["System should automatically categorise complaints by region"]
  reason: future-state recommendation, not a current-state rule.

Correct form:
  business_rules: ["Analyst manually selects complaint category and region from dropdown"]

__TRANSCRIPT__
""".strip()


def _template_hint(document_template: str) -> str:
    return _TEMPLATE_HINTS.get(str(document_template or "pdd").strip().lower(), _TEMPLATE_HINTS["pdd"])


def _should_retry_extraction(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 502, 503}
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return "connection reset" in str(exc).lower()
    return False


def _run_with_transient_retries(operation: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    delay_seconds = 0.5
    for attempt in range(MAX_EXTRACTION_RETRIES + 1):
        try:
            return operation()
        except Exception as exc:
            if attempt >= MAX_EXTRACTION_RETRIES or not _should_retry_extraction(exc):
                raise
            time.sleep(delay_seconds)
            delay_seconds *= 2


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


def _truncate_raw_preview(text: str) -> Optional[str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:MAX_RAW_PREVIEW_CHARS]


def _parse_extraction_text(text: str) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    parsed = _extract_json(text)
    if not parsed:
        return None, _truncate_raw_preview(text)
    return _normalize_extraction(parsed), None


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _dedupe_strings(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


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
        "volumes_or_frequency": _dedupe_strings(_as_list(facts.get("volumes_or_frequency"))),
        "sla_targets": _dedupe_strings(_as_list(facts.get("sla_targets"))),
        "routing_rules": _dedupe_strings(_as_list(facts.get("routing_rules"))),
        "control_requirements": _dedupe_strings(_as_list(facts.get("control_requirements"))),
        "governance_notes": _dedupe_strings(_as_list(facts.get("governance_notes"))),
        "quantified_pain_points": _dedupe_strings(_as_list(facts.get("quantified_pain_points"))),
        "systems": _dedupe_strings(_as_list(facts.get("systems"))),
        "teams": _dedupe_strings(_as_list(facts.get("teams"))),
        "exception_details": _dedupe_strings(_as_list(facts.get("exception_details"))),
    }


def _normalize_effort_data(payload: Dict[str, Any]) -> list[Dict[str, Any]]:
    rows = payload.get("effort_data", [])
    normalized_by_step: dict[int, Dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            step_no = _as_int(row.get("step_no"), 0)
            effort_min = _as_int(row.get("effort_minutes_min"), 0)
            effort_max = _as_int(row.get("effort_minutes_max"), 0)
            if step_no <= 0 or effort_min <= 0 or effort_max <= 0:
                continue
            normalized_by_step[step_no] = {
                "step_no": step_no,
                "effort_minutes_min": min(effort_min, effort_max),
                "effort_minutes_max": max(effort_min, effort_max),
            }
    return [normalized_by_step[key] for key in sorted(normalized_by_step)]


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


def _normalize_sipoc(payload: Dict[str, Any], normalized_steps: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    step_titles = {
        str(step.get("title", "")).strip().lower(): str(step.get("title", "")).strip()
        for step in normalized_steps
        if str(step.get("title", "")).strip()
    }
    rows = payload.get("sipoc", [])
    normalized = []
    seen = set()
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            supplier = str(row.get("supplier", "")).strip() or "upstream_supplier"
            input_ = str(row.get("input", "")).strip() or "process input"
            process_step_raw = str(row.get("process_step", "")).strip()
            process_step = step_titles.get(process_step_raw.lower(), process_step_raw or "unspecified")
            output = str(row.get("output", "")).strip() or "unspecified"
            customer = str(row.get("customer", "")).strip() or "downstream_customer"
            key = (supplier.lower(), input_.lower(), process_step.lower(), output.lower(), customer.lower())
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "supplier": supplier,
                    "input": input_,
                    "process_step": process_step,
                    "output": output,
                    "customer": customer,
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

    sipoc = _normalize_sipoc(payload, normalized_steps)

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


def _compose_prompt_text(
    transcript_text: str,
    document_template: str,
    context_notes: Optional[str],
) -> str:
    transcript_block = transcript_text[:120000] if transcript_text else "No transcript provided."
    sections = []
    sections.append(_template_hint(document_template))
    if context_notes and str(context_notes).strip():
        sections.append(
            "Additional context provided by user:\n"
            f"{str(context_notes).strip()[:2000]}"
        )
    sections.append(f"Source transcript:\n{transcript_block}")
    return "\n\n".join(sections)


def _frame_context_lines(frame_images: list[dict[str, Any]]) -> str:
    if not frame_images:
        return ""
    lines = [
        "Visual frame evidence (timestamp_s | event label | confidence):",
        "Use these to corroborate transcript steps or identify system/UI transitions not "
        "explicit in the text. Do not create process steps from frame evidence alone.",
    ]
    for frame in frame_images[:20]:
        ts = float(frame.get("timestamp_seconds", 0.0))
        reason = str(frame.get("reason", "baseline"))
        conf = float(frame.get("confidence", 0.5))
        lines.append(
            f"  {ts:.2f}s | {reason} | conf {conf:.2f}"
        )
    return "\n".join(lines)


def _google_extract(
    transcript_text: str,
    api_key: str,
    model: str,
    document_template: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
    return_raw_text: bool = False,
) -> Any:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace(
        "__TRANSCRIPT__",
        _compose_prompt_text(
            transcript_text,
            document_template=document_template,
            context_notes=context_notes,
        ),
    )
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
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "maxOutputTokens": MAX_EXTRACTION_OUTPUT_TOKENS,
        },
    }

    def _request() -> Dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
            return response.json()

    data = _run_with_transient_retries(_request)
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    normalized, raw_preview = _parse_extraction_text(text)
    if return_raw_text:
        return normalized, raw_preview
    return normalized


def _openai_extract(
    transcript_text: str,
    api_key: str,
    model: str,
    document_template: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
    return_raw_text: bool = False,
) -> Any:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace(
        "__TRANSCRIPT__",
        _compose_prompt_text(transcript_text, document_template=document_template, context_notes=context_notes),
    )
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
        "max_completion_tokens": MAX_EXTRACTION_OUTPUT_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }

    def _request() -> Dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    data = _run_with_transient_retries(_request)
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    normalized, raw_preview = _parse_extraction_text(text)
    if return_raw_text:
        return normalized, raw_preview
    return normalized


def _azure_openai_extract(
    transcript_text: str,
    api_key: str,
    deployment: str,
    endpoint: str,
    document_template: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
    return_raw_text: bool = False,
) -> Any:
    base = endpoint.rstrip("/")
    # Azure OpenAI OpenAI-compatible v1 format.
    url = f"{base}/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace(
        "__TRANSCRIPT__",
        _compose_prompt_text(transcript_text, document_template=document_template, context_notes=context_notes),
    )
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
        "max_completion_tokens": MAX_EXTRACTION_OUTPUT_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }

    def _request() -> Dict[str, Any]:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            return response.json()

    data = _run_with_transient_retries(_request)
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    normalized, raw_preview = _parse_extraction_text(text)
    if return_raw_text:
        return normalized, raw_preview
    return normalized


def _ollama_extract(
    transcript_text: str,
    model: str,
    base_url: str,
    document_template: str,
    frame_images: Optional[list[dict[str, Any]]] = None,
    context_notes: Optional[str] = None,
    return_raw_text: bool = False,
) -> Any:
    url = f"{base_url.rstrip('/')}/api/generate"
    frame_images = frame_images or []
    prompt = PROMPT_TEMPLATE.replace(
        "__TRANSCRIPT__",
        _compose_prompt_text(
            transcript_text,
            document_template=document_template,
            context_notes=context_notes,
        ),
    )
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
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "images": images,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1, "num_predict": MAX_EXTRACTION_OUTPUT_TOKENS},
    }

    def _request() -> Dict[str, Any]:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=body)
            response.raise_for_status()
            return response.json()

    data = _run_with_transient_retries(_request)
    text = data.get("response", "")
    normalized, raw_preview = _parse_extraction_text(text)
    if return_raw_text:
        return normalized, raw_preview
    return normalized


def extract_with_llm(
    provider: str,
    transcript_text: str,
    document_template: str,
    context_notes: Optional[str],
    api_key: Optional[str],
    model: str,
    ollama_base_url: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    frame_images: Optional[list[dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    result, _error = extract_with_llm_detailed(
        provider=provider,
        transcript_text=transcript_text,
        document_template=document_template,
        context_notes=context_notes,
        api_key=api_key,
        model=model,
        ollama_base_url=ollama_base_url,
        azure_endpoint=azure_endpoint,
        frame_images=frame_images,
    )
    return result


def extract_with_llm_detailed(
    provider: str,
    transcript_text: str,
    document_template: str,
    context_notes: Optional[str],
    api_key: Optional[str],
    model: str,
    ollama_base_url: Optional[str] = None,
    azure_endpoint: Optional[str] = None,
    frame_images: Optional[list[dict[str, Any]]] = None,
) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
    result_raw_preview = None
    frame_images = frame_images or []
    if (not transcript_text and not frame_images) or not api_key:
        if provider != "ollama":
            return None, None
    try:
        if provider == "google":
            result, result_raw_preview = _google_extract(
                transcript_text=transcript_text,
                document_template=document_template,
                context_notes=context_notes,
                api_key=api_key,
                model=model,
                frame_images=frame_images,
                return_raw_text=True,
            )
        elif provider == "azure_openai":
            if not azure_endpoint:
                return None, "Structured extraction skipped: Azure endpoint is missing."
            result, result_raw_preview = _azure_openai_extract(
                transcript_text=transcript_text,
                document_template=document_template,
                context_notes=context_notes,
                api_key=api_key,
                deployment=model,
                endpoint=azure_endpoint,
                frame_images=frame_images,
                return_raw_text=True,
            )
        elif provider == "ollama":
            result, result_raw_preview = _ollama_extract(
                transcript_text=transcript_text,
                document_template=document_template,
                context_notes=context_notes,
                model=model,
                base_url=ollama_base_url or "http://127.0.0.1:11434",
                frame_images=frame_images,
                return_raw_text=True,
            )
        else:
            result, result_raw_preview = _openai_extract(
                transcript_text=transcript_text,
                document_template=document_template,
                context_notes=context_notes,
                api_key=api_key,
                model=model,
                frame_images=frame_images,
                return_raw_text=True,
            )
        if result is None:
            if result_raw_preview:
                return None, f"Structured extraction returned no valid JSON. Raw preview: {result_raw_preview}"
            return None, "Structured extraction returned no valid JSON."
        return result, None
    except Exception as exc:
        logger.exception(
            "structured_extraction_failed provider=%s model=%s document_template=%s transcript_present=%s frame_count=%s",
            provider,
            model,
            document_template,
            bool((transcript_text or "").strip()),
            len(frame_images),
        )
        return None, f"{type(exc).__name__}: {str(exc)[:500]}"
