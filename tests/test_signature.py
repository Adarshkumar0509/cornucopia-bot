import hashlib
import hmac

import pytest

from app.utils.signature import verify_signature


def _make_sig(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def test_valid_signature_returns_true():
    body = b'{"action": "opened"}'
    secret = "mysecret"
    sig = _make_sig(body, secret)
    assert verify_signature(body, secret, sig) is True


def test_invalid_signature_returns_false():
    body = b'{"action": "opened"}'
    secret = "mysecret"
    assert verify_signature(body, secret, "sha256=invalidsignature") is False


def test_tampered_body_fails():
    body = b'{"action": "opened"}'
    secret = "mysecret"
    sig = _make_sig(body, secret)
    tampered = b'{"action": "edited"}'
    assert verify_signature(tampered, secret, sig) is False


def test_missing_signature_returns_false():
    assert verify_signature(b"body", "secret", "") is False


def test_missing_secret_returns_false():
    body = b"body"
    sig = _make_sig(body, "secret")
    assert verify_signature(body, "", sig) is False
