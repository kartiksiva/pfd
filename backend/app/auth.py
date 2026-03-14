import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import Settings

AccessRole = Literal["owner", "guest"]


class AuthError(Exception):
    def __init__(self, message: str = "Authentication required.") -> None:
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AccessSession:
    role: AccessRole
    expires_at: Optional[datetime]


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("utf-8"))


def _sign(payload_b64: str, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return _urlsafe_b64encode(signature)


def create_access_session(role: AccessRole, settings: Settings) -> AccessSession:
    if role == "owner":
        return AccessSession(role="owner", expires_at=None)
    return AccessSession(role="guest", expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.guest_access_timeout_minutes))


def create_session_token(session: AccessSession, settings: Settings) -> str:
    payload = {
        "role": session.role,
        "exp": int(session.expires_at.timestamp()) if session.expires_at else None,
    }
    payload_b64 = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(payload_b64, settings.access_session_secret)
    return f"{payload_b64}.{signature}"


def read_session_token(token: str, settings: Settings) -> AccessSession:
    try:
        payload_b64, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthError("Authentication required.") from exc

    expected_signature = _sign(payload_b64, settings.access_session_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthError("Authentication required.")

    try:
        payload = json.loads(_urlsafe_b64decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError("Authentication required.") from exc

    role = payload.get("role")
    if role not in {"owner", "guest"}:
        raise AuthError("Authentication required.")

    exp = payload.get("exp")
    if exp is None:
        return AccessSession(role=role, expires_at=None)

    try:
        expires_at = datetime.fromtimestamp(int(exp), tz=timezone.utc)
    except (TypeError, ValueError, OSError) as exc:
        raise AuthError("Authentication required.") from exc

    if expires_at <= datetime.now(timezone.utc):
        raise AuthError("Session expired. Enter the access code again.")

    return AccessSession(role=role, expires_at=expires_at)


def get_authenticated_session(request: Request, settings: Settings) -> AccessSession:
    token = request.cookies.get(settings.access_cookie_name)
    if not token:
        raise AuthError("Authentication required.")
    return read_session_token(token, settings)


def validate_access_code(code: str, settings: Settings) -> AccessSession:
    trimmed_code = code.strip()
    if trimmed_code == settings.owner_access_code:
        return create_access_session("owner", settings)
    if trimmed_code == settings.guest_access_code:
        return create_access_session("guest", settings)
    raise AuthError("Incorrect code.")


def attach_session_cookie(response: JSONResponse, session: AccessSession, settings: Settings) -> None:
    max_age = None if session.expires_at is None else max(1, int((session.expires_at - datetime.now(timezone.utc)).total_seconds()))
    response.set_cookie(
        key=settings.access_cookie_name,
        value=create_session_token(session, settings),
        httponly=True,
        secure=settings.access_cookie_secure,
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_session_cookie(response: JSONResponse, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.access_cookie_name,
        httponly=True,
        secure=settings.access_cookie_secure,
        samesite="lax",
        path="/",
    )
