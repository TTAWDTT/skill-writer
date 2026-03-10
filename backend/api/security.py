"""
API security helpers.
"""
from __future__ import annotations

from typing import Optional
import re

from fastapi import HTTPException, Request

_BEARER_RE = re.compile(r"^\s*Bearer\s+(.+?)\s*$", re.IGNORECASE)


def get_bearer_token(request: Request, *, allow_query: bool = False) -> Optional[str]:
    """Extract bearer token from Authorization header (or query when allowed)."""
    auth = request.headers.get("Authorization", "")
    if auth:
        match = _BEARER_RE.match(auth)
        if match:
            token = (match.group(1) or "").strip()
            if token:
                return token

    if allow_query:
        for key in ("access_token", "token"):
            value = (request.query_params.get(key) or "").strip()
            if value:
                return value

    return None


def require_bearer_token(request: Request, *, allow_query: bool = False) -> str:
    """Require bearer token for protected APIs."""
    token = get_bearer_token(request, allow_query=allow_query)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if len(token) < 16:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return token
