from hmac import compare_digest

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(key: str | None = Depends(api_key_header)) -> str:
    if not key or not settings.agent_api_key or not compare_digest(
        key.encode(), settings.agent_api_key.encode()
    ):
        raise HTTPException(401, "Invalid or missing API key")
    return key
