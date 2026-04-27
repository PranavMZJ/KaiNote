"""WebSocket $connect Lambda authorizer for API Gateway.

Validates JWT tokens from the query string parameter ``token`` against
Cognito JWKS public keys.  Returns an IAM Allow/Deny policy document.

Environment variables:
    COGNITO_USER_POOL_ID – Cognito User Pool ID (e.g. ap-northeast-1_XXXXXXX)
    COGNITO_JWKS_URL     – Full URL to the JWKS endpoint for the pool

Requirements: 1.3, 1.4, 3.5, 13.2
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.request import urlopen

import jwt  # PyJWT

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Module-level JWKS cache (persists across warm Lambda invocations)
# ---------------------------------------------------------------------------
_jwks_cache: Optional[Dict[str, Any]] = None
_jwks_cache_time: float = 0.0
_JWKS_CACHE_TTL_SECONDS: int = 3600  # 1 hour


def _get_jwks(jwks_url: str, *, _force: bool = False) -> Dict[str, Any]:
    """Fetch and cache the Cognito JWKS key set.

    Keys are cached in a module-level variable so that subsequent
    invocations on the same warm Lambda container skip the HTTP call.
    """
    global _jwks_cache, _jwks_cache_time  # noqa: PLW0603

    now = time.time()
    if not _force and _jwks_cache is not None and (now - _jwks_cache_time) < _JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    logger.info("Fetching JWKS from %s", jwks_url)
    with urlopen(jwks_url) as resp:  # noqa: S310 – URL comes from env var
        data = json.loads(resp.read().decode("utf-8"))

    _jwks_cache = data
    _jwks_cache_time = now
    return data


def _get_signing_key(token: str, jwks: Dict[str, Any]) -> jwt.algorithms.RSAAlgorithm:
    """Find the correct public key from the JWKS set for the given token."""
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    if kid is None:
        raise ValueError("Token header missing 'kid'")

    for key_data in jwks.get("keys", []):
        if key_data["kid"] == kid:
            return jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

    raise ValueError(f"Public key not found for kid={kid}")


def _build_policy(
    principal_id: str,
    effect: str,
    method_arn: str,
    context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build an IAM policy document for API Gateway authorizer response."""
    policy: Dict[str, Any] = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": method_arn,
                }
            ],
        },
    }
    if context:
        policy["context"] = context
    return policy


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for WebSocket $connect authorizer.

    Extracts the JWT from ``event["queryStringParameters"]["token"]``,
    verifies it against Cognito JWKS, and returns an Allow or Deny policy.
    """
    method_arn: str = event.get("methodArn", "")
    logger.info("Authorizer invoked – methodArn=%s", method_arn)

    # --- Extract token from query string -----------------------------------
    query_params = event.get("queryStringParameters") or {}
    token = query_params.get("token")

    if not token:
        logger.warning("No token in query string parameters")
        return _build_policy("unauthorized", "Deny", method_arn)

    # --- Environment -------------------------------------------------------
    user_pool_id = os.environ.get("COGNITO_USER_POOL_ID", "")
    jwks_url = os.environ.get("COGNITO_JWKS_URL", "")
    region = jwks_url.split("//cognito-idp.")[-1].split(".amazonaws.com")[0] if jwks_url else ""
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"

    try:
        # --- Fetch JWKS and find signing key --------------------------------
        jwks = _get_jwks(jwks_url)
        public_key = _get_signing_key(token, jwks)

        # --- Verify JWT -----------------------------------------------------
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=issuer,
            options={
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": False,  # Cognito access tokens use 'client_id' not 'aud'
            },
        )

        user_sub: str = claims.get("sub", "unknown")
        logger.info("Token verified – sub=%s", user_sub)

        return _build_policy(
            principal_id=user_sub,
            effect="Allow",
            method_arn=method_arn,
            context={"userId": user_sub},
        )

    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        return _build_policy("unauthorized", "Deny", method_arn)
    except jwt.InvalidIssuerError:
        logger.warning("Invalid token issuer")
        return _build_policy("unauthorized", "Deny", method_arn)
    except jwt.InvalidTokenError as exc:
        logger.warning("Invalid token: %s", exc)
        return _build_policy("unauthorized", "Deny", method_arn)
    except Exception:
        logger.exception("Unexpected error during token verification")
        return _build_policy("unauthorized", "Deny", method_arn)
