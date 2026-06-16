from fastapi import Header
from fastapi import HTTPException
from fastapi import Query

from .config import settings


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    api_key: str | None = Query(default=None),
):
    if not settings.api_keys:
        return  # auth disabled
    provided = x_api_key or api_key
    if provided not in settings.api_keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
