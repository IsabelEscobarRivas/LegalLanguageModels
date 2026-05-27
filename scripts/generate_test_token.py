"""Generate a JWT for QA against Sprint 5 endpoints.

This script is the QA testing surface for auth. Sprint 5 has no token
issuance endpoint by design; tokens are minted manually here and pasted into
client requests.

Usage:
    JWT_SECRET=... python scripts/generate_test_token.py \\
        --sub user-123 \\
        --firm-id 8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b \\
        [--role admin] \\
        [--expires-in-hours 24]

The default QA firm_id matches migration 0010 DEFAULT_FIRM_ID (Default Firm).

The script writes the token to stdout and nothing else, so it composes:

    TOKEN=$(JWT_SECRET=secret python scripts/generate_test_token.py \\
        --sub u --firm-id 8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b)
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/...
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt


JWT_ALGORITHM = "HS256"
DEFAULT_FIRM_ID = "8f3e2a1b-4c5d-6e7f-8a9b-0c1d2e3f4a5b"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a test JWT (HS256) for Sprint 5 endpoints."
    )
    parser.add_argument(
        "--sub",
        required=True,
        help="Subject claim — user identifier.",
    )
    parser.add_argument(
        "--firm-id",
        required=True,
        metavar="FIRM_ID",
        help=(
            "Firm UUID this token scopes access to "
            f"(default QA firm: {DEFAULT_FIRM_ID})."
        ),
    )
    parser.add_argument(
        "--role",
        default=None,
        help="Optional role claim (e.g. 'admin', 'paralegal').",
    )
    parser.add_argument(
        "--expires-in-hours",
        type=float,
        default=24.0,
        help="Token lifetime in hours from now (default: 24).",
    )
    args = parser.parse_args()

    secret = os.environ.get("JWT_SECRET")
    if not secret:
        print("ERROR: JWT_SECRET environment variable is required", file=sys.stderr)
        return 1

    now = datetime.now(tz=timezone.utc)
    payload: dict = {
        "sub": args.sub,
        "firm_id": args.firm_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=args.expires_in_hours)).timestamp()),
    }
    if args.role is not None:
        payload["role"] = args.role

    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
