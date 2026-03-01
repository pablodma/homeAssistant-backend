import time

import pytest
from fastapi import HTTPException
from jose import jwt

from src.app.routers.onboarding import (
    _decode_onboarding_token,
    _encode_opaque_onboarding_token,
)


def test_decode_onboarding_token_accepts_opaque_format() -> None:
    secret = "test-onboarding-secret"
    phone = "+5491112345678"
    token = _encode_opaque_onboarding_token(
        phone=phone,
        exp=int(time.time()) + 3600,
        secret=secret,
    )

    resolved_phone = _decode_onboarding_token(token, secret)

    assert resolved_phone == phone


def test_decode_onboarding_token_accepts_legacy_jwt_format() -> None:
    secret = "test-onboarding-secret"
    phone = "+5491112345678"
    token = jwt.encode(
        {"phone": phone, "exp": int(time.time()) + 3600},
        secret,
        algorithm="HS256",
    )

    resolved_phone = _decode_onboarding_token(token, secret)

    assert resolved_phone == phone


def test_decode_onboarding_token_rejects_expired_opaque_token() -> None:
    secret = "test-onboarding-secret"
    token = _encode_opaque_onboarding_token(
        phone="+5491112345678",
        exp=int(time.time()) - 10,
        secret=secret,
    )

    with pytest.raises(HTTPException) as exc:
        _decode_onboarding_token(token, secret)

    assert exc.value.status_code == 400
    assert exc.value.detail == "Invalid or expired onboarding token"
