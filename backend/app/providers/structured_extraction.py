import json
import re
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
  "exceptions": ["string"],
  "outputs": ["string"],
  "metrics": ["string"],
  "risks": ["string"],
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
- Keep confidence between 0.0 and 1.0.

Source transcript:
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
        "exceptions": _as_list(payload.get("exceptions")),
        "outputs": _as_list(payload.get("outputs")),
        "metrics": _as_list(payload.get("metrics")),
        "risks": _as_list(payload.get("risks")),
        "sipoc": sipoc,
        "confidence": confidence,
    }


def _google_extract(transcript_text: str, api_key: str, model: str) -> Optional[Dict[str, Any]]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", transcript_text[:120000])
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }
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


def _openai_extract(transcript_text: str, api_key: str, model: str) -> Optional[Dict[str, Any]]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", transcript_text[:120000])
    body = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You extract business process structure and return strict JSON only."},
            {"role": "user", "content": prompt},
        ],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    parsed = _extract_json(text)
    return _normalize_extraction(parsed) if parsed else None


def _ollama_extract(transcript_text: str, model: str, base_url: str) -> Optional[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/generate"
    prompt = PROMPT_TEMPLATE.replace("__TRANSCRIPT__", transcript_text[:120000])
    body = {
        "model": model,
        "prompt": prompt,
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
    api_key: Optional[str],
    model: str,
    ollama_base_url: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not transcript_text or not api_key:
        if provider != "ollama":
            return None
    try:
        if provider == "google":
            return _google_extract(transcript_text=transcript_text, api_key=api_key, model=model)
        if provider == "ollama":
            return _ollama_extract(transcript_text=transcript_text, model=model, base_url=ollama_base_url or "http://127.0.0.1:11434")
        return _openai_extract(transcript_text=transcript_text, api_key=api_key, model=model)
    except Exception:
        return None
