import httpx
from fastapi import APIRouter
from fastapi import Depends

from ..auth import require_api_key
from ..config import settings

router = APIRouter(prefix="/api/v1")


@router.get("/models", dependencies=[Depends(require_api_key)])
async def list_models():
    """Proxy the upstream OpenAI-compatible /models endpoint for the picker."""
    url = settings.translation_base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {settings.translation_api_key}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        ids = [m["id"] for m in data.get("data", []) if "id" in m]
    except Exception:
        ids = []
    if settings.translation_model not in ids:
        ids.insert(0, settings.translation_model)
    return {"default": settings.translation_model, "models": ids}
