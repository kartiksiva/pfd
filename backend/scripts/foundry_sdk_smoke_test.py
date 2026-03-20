#!/usr/bin/env python3
"""
Foundry/OpenAI Azure smoke test.

Usage:
  .venv/bin/python scripts/foundry_sdk_smoke_test.py --mode foundry
  .venv/bin/python scripts/foundry_sdk_smoke_test.py --mode openai_v1
  .venv/bin/python scripts/foundry_sdk_smoke_test.py --mode both

Required env vars:
  For --mode foundry:
    AZURE_FOUNDRY_PROJECT_ENDPOINT
    AZURE_OPENAI_CHAT_DEPLOYMENT

  For --mode openai_v1:
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_CHAT_DEPLOYMENT
    AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT
"""

from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import sys
import wave
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from openai import OpenAI
from app.config import get_settings


def _tiny_wav_bytes() -> bytes:
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    return audio.getvalue()


def _read_dotenv_value(name: str) -> str:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""


def _require(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        value = _read_dotenv_value(name)
    if not value:
        settings = get_settings()
        fallback = {
            "AZURE_OPENAI_API_KEY": settings.azure_openai_api_key,
            "AZURE_OPENAI_ENDPOINT": settings.azure_openai_endpoint,
            "AZURE_OPENAI_CHAT_DEPLOYMENT": settings.azure_openai_chat_deployment,
            "AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT": settings.azure_openai_transcription_deployment,
        }.get(name)
        value = (fallback or "").strip()
    if not value:
        raise RuntimeError(f"missing_env:{name}")
    return value


def _run_foundry_sdk_chat() -> bool:
    endpoint = _require("AZURE_FOUNDRY_PROJECT_ENDPOINT")
    model = _require("AZURE_OPENAI_CHAT_DEPLOYMENT")
    print(f"[foundry] endpoint={endpoint}")
    print(f"[foundry] model={model}")
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
    client = AIProjectClient(endpoint=endpoint, credential=credential)
    oai = client.get_openai_client()
    resp = oai.responses.create(
        model=model,
        input="Reply with exactly OK",
    )
    text = (getattr(resp, "output_text", "") or "").strip()
    print(f"[foundry] responses_ok=True response={text[:120]!r}")
    return True


def _run_openai_v1_chat_and_transcription() -> bool:
    endpoint = _require("AZURE_OPENAI_ENDPOINT").rstrip("/")
    api_key = _require("AZURE_OPENAI_API_KEY")
    chat_model = _require("AZURE_OPENAI_CHAT_DEPLOYMENT")
    tx_model = _require("AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT")
    base_url = f"{endpoint}/openai/v1/"
    print(f"[openai_v1] base_url={base_url}")
    print(f"[openai_v1] chat_model={chat_model}")
    print(f"[openai_v1] tx_model={tx_model}")
    client = OpenAI(base_url=base_url, api_key=api_key)

    chat = client.chat.completions.create(
        model=chat_model,
        messages=[{"role": "user", "content": "Reply with exactly OK"}],
        max_completion_tokens=32,
    )
    chat_text = (chat.choices[0].message.content or "").strip() if chat.choices else ""
    print(f"[openai_v1] chat_ok=True response={chat_text[:120]!r}")

    wav_bytes = _tiny_wav_bytes()
    tx = client.audio.transcriptions.create(
        model=tx_model,
        file=("test.wav", wav_bytes, "audio/wav"),
        language="en",
        response_format="json",
    )
    tx_text = getattr(tx, "text", "") if tx is not None else ""
    print(f"[openai_v1] transcription_ok=True text={str(tx_text)[:120]!r}")
    return True


def _run(mode: str) -> int:
    foundry_ok: Optional[bool] = None
    v1_ok: Optional[bool] = None

    if mode in {"foundry", "both"}:
        try:
            foundry_ok = _run_foundry_sdk_chat()
        except Exception as exc:
            foundry_ok = False
            print(f"[foundry] chat_ok=False error={exc}")

    if mode in {"openai_v1", "both"}:
        try:
            v1_ok = _run_openai_v1_chat_and_transcription()
        except Exception as exc:
            v1_ok = False
            print(f"[openai_v1] smoke_ok=False error={exc}")

    ok_values = [x for x in (foundry_ok, v1_ok) if x is not None]
    return 0 if ok_values and all(ok_values) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Foundry/OpenAI Azure smoke test")
    parser.add_argument(
        "--mode",
        choices=("foundry", "openai_v1", "both"),
        default="both",
        help="Which path to test",
    )
    args = parser.parse_args()
    return _run(args.mode)


if __name__ == "__main__":
    sys.exit(main())
