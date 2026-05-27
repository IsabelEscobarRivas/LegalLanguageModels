"""JWT verification for Sprint 5 endpoints.

HS256, secret from `JWT_SECRET` env var. Required claims: `exp`, `sub`, `firm_id`.
Optional claims: `role`, `iat`. No `iss` or `aud` validation in Sprint 5.

Two public APIs:
  - get_current_claims:  validates the bearer token, returns TokenClaims
  - require_case_access: confirms the path's case belongs to the token's firm_id
"""
from dataclasses import dataclass
from typing import Optional
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Case


# Sprint 2 has no token issuance endpoint; `tokenUrl` is a placeholder so
# Swagger UI still shows the Authorize button (operators paste tokens directly).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

JWT_ALGORITHM = "HS256"


@dataclass
class TokenClaims:
    sub: str
    firm_id: str
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
            options={"require": ["exp", "sub", "firm_id"]},
        )
    except jwt.PyJWTError:
        raise _invalid_token_exception()

    sub = payload.get("sub")
    firm_id = payload.get("firm_id")
    role = payload.get("role")

    if not isinstance(sub, str) or not sub:
        raise _invalid_token_exception()
    if not isinstance(firm_id, str) or not firm_id:
        raise _invalid_token_exception()
    if role is not None and not isinstance(role, str):
        raise _invalid_token_exception()

    return TokenClaims(sub=sub, firm_id=firm_id, role=role)


def require_case_access(
    case_id: str,
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
) -> str:
    """Confirm the path's case belongs to the token's firm.

    Returns the `case_id` unchanged so it can be used directly in endpoint
    signatures, e.g. `case_id: str = Depends(require_case_access)`.

    Raises 404 if the case is not found or not owned by the token's firm.
    """
    case = (
        db.query(Case)
        .filter(Case.id == case_id, Case.firm_id == claims.firm_id)
        .first()
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case_id
