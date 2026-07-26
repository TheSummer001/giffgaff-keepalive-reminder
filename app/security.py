from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class InvalidToken(ValueError):
    pass


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_token(
    secret: str,
    purpose: str,
    *,
    expires_in_seconds: int,
    extra: dict[str, Any] | None = None,
) -> str:
    payload: dict[str, Any] = {
        "purpose": purpose,
        "exp": int(time.time()) + expires_in_seconds,
    }
    if extra:
        payload.update(extra)
    encoded = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = hmac.new(
        secret.encode(), encoded.encode(), hashlib.sha256
    ).digest()
    return f"{encoded}.{_b64encode(signature)}"


def verify_token(secret: str, token: str, purpose: str) -> dict[str, Any]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            secret.encode(), encoded.encode(), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(
            _b64decode(supplied_signature), expected_signature
        ):
            raise InvalidToken("invalid signature")
        payload = json.loads(_b64decode(encoded))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise InvalidToken("malformed token") from exc

    if payload.get("purpose") != purpose:
        raise InvalidToken("wrong token purpose")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise InvalidToken("token expired")
    return payload
