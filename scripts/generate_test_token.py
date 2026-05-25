"""Generate a JWT for QA against Sprint 2 endpoints.

This script is the QA testing surface for Step 3. Sprint 2 has no token
issuance endpoint by design; tokens are minted manually here and pasted into
client requests.

Usage:
    JWT_SECRET=... python scripts/generate_test_token.py \\
        --sub user-123 \\
        --case-ids <uuid-1> <uuid-2> \\
        [--role admin] \\
        [--expires-in-hours 24]

The script writes the token to stdout and nothing else, so it composes:

    TOKEN=$(JWT_SECRET=secret python scripts/generate_test_token.py \\
        --sub u --case-ids c1)
    curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/...
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import jwt


JWT_ALGORITHM = "HS256"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a test JWT (HS256) for Sprint 2 endpoints."
    )
    parser.add_argument(
        "--sub",
        required=True,
        help="Subject claim — user identifier.",
    )
    parser.add_argument(
        "--case-ids",
        nargs="+",
        required=True,
        metavar="CASE_ID",
        help="One or more case UUIDs this token authorizes access to.",
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
        "case_ids": list(args.case_ids),
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
