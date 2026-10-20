import logging
from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from app.config import get_settings
from app.models.alert import AlertPayload
from app.services.parser import parse_tradingview_payload

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Webhook"])


def _verify_secret(
    configured_secret: str,
    path_secret: Optional[str] = None,
    query_secret: Optional[str] = None,
    header_secret: Optional[str] = None,
    payload_passphrase: Optional[str] = None,
) -> bool:
    """Validate incoming secret against configured WEBHOOK_SECRET."""
    # If no secret configured or default disabled, allow (with warning)
    if not configured_secret or configured_secret == "change_me_in_production":
        return True

    candidates = [
        path_secret,
        query_secret,
        header_secret,
        payload_passphrase,
    ]
    return any(c is not None and c.strip() == configured_secret for c in candidates)


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook(
    request: Request,
    secret: Optional[str] = Query(default=None),
    x_webhook_secret: Optional[str] = Header(default=None, alias="X-Webhook-Secret"),
):
    """Receive TradingView alert webhook.

    Authenticates via query param (?secret=...), header (X-Webhook-Secret), or JSON passphrase.
    """
    settings = get_settings()
    raw_bytes = await request.body()
    alert: AlertPayload = parse_tradingview_payload(raw_bytes)

    if not _verify_secret(
        configured_secret=settings.WEBHOOK_SECRET,
        query_secret=secret,
        header_secret=x_webhook_secret,
        payload_passphrase=alert.passphrase,
    ):
        logger.warning("Rejected unauthenticated webhook request from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing webhook passphrase/secret.",
        )

    queue_service = getattr(request.app.state, "queue_service", None)
    if queue_service:
        enqueued = queue_service.enqueue(alert)
        if not enqueued:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Alert queue buffer is full. Dropping request to prevent memory leak.",
            )

    logger.info("Alert ingested successfully: %s %s @ %s", alert.ticker, alert.action, alert.price)
    return {
        "status": "queued",
        "ticker": alert.ticker,
        "action": alert.normalized_action,
        "price": alert.price,
    }


@router.post("/webhook/{secret_token}", status_code=status.HTTP_202_ACCEPTED)
async def receive_webhook_with_token(
    secret_token: str,
    request: Request,
):
    """Receive TradingView alert webhook with secret token embedded in the URL path.

    Recommended TradingView webhook URL format:
    https://your-domain.com/webhook/your_super_secret_token
    """
    settings = get_settings()
    raw_bytes = await request.body()
    alert: AlertPayload = parse_tradingview_payload(raw_bytes)

    if not _verify_secret(
        configured_secret=settings.WEBHOOK_SECRET,
        path_secret=secret_token,
        payload_passphrase=alert.passphrase,
    ):
        logger.warning("Rejected unauthenticated webhook URL token from %s", request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid secret token in webhook URL path.",
        )

    queue_service = getattr(request.app.state, "queue_service", None)
    if queue_service:
        enqueued = queue_service.enqueue(alert)
        if not enqueued:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Alert queue buffer is full. Dropping request to prevent memory leak.",
            )

    logger.info("Alert ingested via path token: %s %s @ %s", alert.ticker, alert.action, alert.price)
    return {
        "status": "queued",
        "ticker": alert.ticker,
        "action": alert.normalized_action,
        "price": alert.price,
    }
