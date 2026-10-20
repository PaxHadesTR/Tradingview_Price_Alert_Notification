from datetime import datetime, timezone
from fastapi import APIRouter, Request

router = APIRouter(tags=["Health"])


@router.get("/healthz")
async def healthcheck(request: Request):
    """Coolify liveness and readiness probe endpoint."""
    queue_service = getattr(request.app.state, "queue_service", None)
    stats = queue_service.stats if queue_service else {}
    return {
        "status": "healthy",
        "service": "Tradingview_Price_Alert_Notification",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue": stats,
    }


@router.get("/live")
async def liveness():
    """Simple ping for reverse proxies and uptime monitors."""
    return {"status": "ok"}
