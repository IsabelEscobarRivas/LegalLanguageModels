"""JWT verification for Sprint 2 endpoints.

HS256, secret from `JWT_SECRET` env var. Required claims: `exp`, `sub`, `case_ids`.
Optional claims: `role`, `iat`. No `iss` or `aud` validation in Sprint 2.

Two public APIs:
  - get_current_claims:  validates the bearer token, returns TokenClaims
  - require_case_access: asserts the path's case_id is in the claims, returns case_id
"""
from dataclasses import dataclass
from typing import Optional
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer


# Sprint 2 has no token issuance endpoint; `tokenUrl` is a placeholder so
# Swagger UI still shows the Authorize button (operators paste tokens directly).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

JWT_ALGORITHM = "HS256"


@dataclass
class TokenClaims:
    sub: str
    case_ids: list[str]
    role: Optional[str] = None


def _invalid_token_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_claims(token: str = Depends(oauth2_scheme)) -> TokenClaims:
    """Validate the bearer token and return its claims.

    Missing token: FastAPI's `OAuth2PasswordBearer` auto-raises 401 with the
    `WWW-Authenticate: Bearer` header. This function is never reached in that
    case.

    Invalid signature, expired, missing required claims, or wrong claim types:
    raise 401 with `{"detail": "Invalid or expired token"}`.

    Server-side misconfiguration (no JWT_SECRET): raise 500 — that's a server
    problem, not a client problem, and we don't pretend the token is bad.
    """
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Auth misconfigured",
        )

    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise _invalid_token_exception()

    sub = payload.get("sub")
    case_ids = payload.get("case_ids")
    role = payload.get("role")

    if not isinstance(sub, str) or not sub:
        raise _invalid_token_exception()
    if not isinstance(case_ids, list) or not all(
        isinstance(c, str) for c in case_ids
    ):
        raise _invalid_token_exception()
    if role is not None and not isinstance(role, str):
        raise _invalid_token_exception()

    return TokenClaims(sub=sub, case_ids=list(case_ids), role=role)


def require_case_access(
    case_id: str,
    claims: TokenClaims = Depends(get_current_claims),
) -> str:
    """Confirm the path's `case_id` is in the token's `case_ids` claim.

    Returns the `case_id` unchanged so it can be used directly in endpoint
    signatures, e.g. `case_id: str = Depends(require_case_access)`.

    Raises 403 if the case is not in the token's authorized list.
    """
    if case_id not in claims.case_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this case is not permitted",
        )
    return case_id
