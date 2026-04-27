"""Unit tests for the WebSocket authorizer Lambda handler.

Tests cover:
- Token extraction from query string parameters
- JWT verification (valid token, expired, bad issuer, bad signature)
- JWKS caching behaviour
- IAM policy document structure (Allow / Deny)
- Missing token returns Deny

Requirements: 1.3, 1.4, 3.5, 13.2
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from backend.lambdas.ws_authorizer import handler as authorizer_module
from backend.lambdas.ws_authorizer.handler import (
    _build_policy,
    _get_jwks,
    _get_signing_key,
    handler,
)


# ---------------------------------------------------------------------------
# Helpers – RSA key pair & JWT generation
# ---------------------------------------------------------------------------

def _generate_rsa_keypair():
    """Generate a fresh RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    return private_key


def _private_key_to_pem(private_key) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _build_jwks(private_key, kid: str = "test-kid-1") -> Dict[str, Any]:
    """Build a JWKS dict from an RSA private key."""
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    def _int_to_base64url(n: int, length: int) -> str:
        import base64
        data = n.to_bytes(length, byteorder="big")
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": kid,
                "use": "sig",
                "alg": "RS256",
                "n": _int_to_base64url(public_numbers.n, 256),
                "e": _int_to_base64url(public_numbers.e, 3),
            }
        ]
    }


def _make_token(
    private_key,
    kid: str = "test-kid-1",
    sub: str = "user-abc-123",
    issuer: str = "https://cognito-idp.ap-northeast-1.amazonaws.com/ap-northeast-1_TestPool",
    exp_offset: int = 3600,
    extra_claims: Dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT for testing."""
    now = int(time.time())
    payload: Dict[str, Any] = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "exp": now + exp_offset,
        "token_use": "access",
        "client_id": "test-client-id",
    }
    if extra_claims:
        payload.update(extra_claims)

    return pyjwt.encode(
        payload,
        _private_key_to_pem(private_key),
        algorithm="RS256",
        headers={"kid": kid},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

USER_POOL_ID = "ap-northeast-1_TestPool"
JWKS_URL = f"https://cognito-idp.ap-northeast-1.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
ISSUER = f"https://cognito-idp.ap-northeast-1.amazonaws.com/{USER_POOL_ID}"
METHOD_ARN = "arn:aws:execute-api:ap-northeast-1:123456789012:abc123/prod/$connect"


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    """Clear the module-level JWKS cache before each test."""
    authorizer_module._jwks_cache = None
    authorizer_module._jwks_cache_time = 0.0
    yield
    authorizer_module._jwks_cache = None
    authorizer_module._jwks_cache_time = 0.0


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables."""
    monkeypatch.setenv("COGNITO_USER_POOL_ID", USER_POOL_ID)
    monkeypatch.setenv("COGNITO_JWKS_URL", JWKS_URL)


@pytest.fixture()
def rsa_key():
    return _generate_rsa_keypair()


# ---------------------------------------------------------------------------
# _build_policy
# ---------------------------------------------------------------------------


class TestBuildPolicy:
    def test_allow_policy_structure(self):
        policy = _build_policy("user-1", "Allow", METHOD_ARN, {"userId": "user-1"})
        assert policy["principalId"] == "user-1"
        stmt = policy["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Allow"
        assert stmt["Action"] == "execute-api:Invoke"
        assert stmt["Resource"] == METHOD_ARN
        assert policy["context"]["userId"] == "user-1"

    def test_deny_policy_structure(self):
        policy = _build_policy("unauthorized", "Deny", METHOD_ARN)
        assert policy["principalId"] == "unauthorized"
        stmt = policy["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"
        assert "context" not in policy

    def test_policy_version(self):
        policy = _build_policy("x", "Allow", METHOD_ARN)
        assert policy["policyDocument"]["Version"] == "2012-10-17"


# ---------------------------------------------------------------------------
# _get_signing_key
# ---------------------------------------------------------------------------


class TestGetSigningKey:
    def test_finds_matching_kid(self, rsa_key):
        jwks = _build_jwks(rsa_key, kid="kid-A")
        token = _make_token(rsa_key, kid="kid-A")
        key = _get_signing_key(token, jwks)
        assert key is not None

    def test_raises_on_missing_kid(self, rsa_key):
        jwks = _build_jwks(rsa_key, kid="kid-A")
        token = _make_token(rsa_key, kid="kid-B")
        with pytest.raises(ValueError, match="Public key not found"):
            _get_signing_key(token, jwks)

    def test_raises_on_no_kid_in_header(self, rsa_key):
        """Token without kid header should raise."""
        payload = {"sub": "u1", "iss": ISSUER, "exp": int(time.time()) + 3600}
        token = pyjwt.encode(
            payload,
            _private_key_to_pem(rsa_key),
            algorithm="RS256",
            headers={},  # no kid
        )
        jwks = _build_jwks(rsa_key)
        with pytest.raises(ValueError, match="missing 'kid'"):
            _get_signing_key(token, jwks)


# ---------------------------------------------------------------------------
# _get_jwks (caching)
# ---------------------------------------------------------------------------


class TestGetJwks:
    def test_fetches_and_caches(self, rsa_key):
        jwks = _build_jwks(rsa_key)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp) as mock_url:
            result1 = _get_jwks(JWKS_URL)
            result2 = _get_jwks(JWKS_URL)

        assert result1 == jwks
        assert result2 == jwks
        # Should only fetch once due to caching
        assert mock_url.call_count == 1

    def test_refetches_after_ttl(self, rsa_key):
        jwks = _build_jwks(rsa_key)
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp) as mock_url:
            _get_jwks(JWKS_URL)
            # Expire the cache
            authorizer_module._jwks_cache_time = time.time() - 7200
            _get_jwks(JWKS_URL)

        assert mock_url.call_count == 2


# ---------------------------------------------------------------------------
# handler – integration-style tests
# ---------------------------------------------------------------------------


class TestHandler:
    def _event(self, token: str | None = None) -> Dict[str, Any]:
        """Build a minimal WebSocket $connect authorizer event."""
        event: Dict[str, Any] = {"methodArn": METHOD_ARN}
        if token is not None:
            event["queryStringParameters"] = {"token": token}
        else:
            event["queryStringParameters"] = {}
        return event

    def test_valid_token_returns_allow(self, rsa_key):
        jwks = _build_jwks(rsa_key)
        token = _make_token(rsa_key, sub="user-xyz")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp):
            result = handler(self._event(token), None)

        assert result["principalId"] == "user-xyz"
        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Allow"
        assert result["context"]["userId"] == "user-xyz"

    def test_missing_token_returns_deny(self):
        result = handler(self._event(token=None), None)
        assert result["principalId"] == "unauthorized"
        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"

    def test_no_query_string_params_returns_deny(self):
        event = {"methodArn": METHOD_ARN}
        result = handler(event, None)
        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"

    def test_expired_token_returns_deny(self, rsa_key):
        jwks = _build_jwks(rsa_key)
        token = _make_token(rsa_key, exp_offset=-3600)  # already expired

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp):
            result = handler(self._event(token), None)

        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"

    def test_wrong_issuer_returns_deny(self, rsa_key):
        jwks = _build_jwks(rsa_key)
        token = _make_token(
            rsa_key,
            issuer="https://cognito-idp.us-east-1.amazonaws.com/us-east-1_Wrong",
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp):
            result = handler(self._event(token), None)

        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"

    def test_tampered_token_returns_deny(self, rsa_key):
        """Token signed with a different key should be rejected."""
        other_key = _generate_rsa_keypair()
        jwks = _build_jwks(rsa_key)  # JWKS has rsa_key's public key
        token = _make_token(other_key, kid="test-kid-1")  # signed with other_key

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp):
            result = handler(self._event(token), None)

        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"

    def test_garbage_token_returns_deny(self):
        result = handler(self._event("not.a.jwt"), None)
        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Effect"] == "Deny"

    def test_method_arn_in_policy(self, rsa_key):
        jwks = _build_jwks(rsa_key)
        token = _make_token(rsa_key)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(jwks).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("backend.lambdas.ws_authorizer.handler.urlopen", return_value=mock_resp):
            result = handler(self._event(token), None)

        stmt = result["policyDocument"]["Statement"][0]
        assert stmt["Resource"] == METHOD_ARN
