from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AlertAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"
    ALERT = "ALERT"
    INFO = "INFO"


class AlertPayload(BaseModel):
    """Normalized internal representation of an alert dispatched from TradingView."""

    passphrase: Optional[str] = Field(
        default=None,
        description="Optional security passphrase provided inside the alert payload",
    )
    ticker: str = Field(
        default="UNKNOWN",
        description="Trading pair or asset symbol (e.g., BTCUSDT, ETHUSD, AAPL)",
    )
    action: Optional[str] = Field(
        default="ALERT",
        description="Triggered action (BUY, SELL, LONG, SHORT, CLOSE, etc.)",
    )
    price: Optional[float] = Field(
        default=None,
        description="Asset price when alert fired",
    )
    strategy: Optional[str] = Field(
        default=None,
        description="Name of the strategy, indicator, or alert condition",
    )
    timeframe: Optional[str] = Field(
        default=None,
        description="Chart timeframe (e.g., 1m, 5m, 15m, 1h, 4h, 1D)",
    )
    message: Optional[str] = Field(
        default=None,
        description="Human-readable text message or additional context",
    )
    timestamp: Optional[str] = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of alert ingestion",
    )
    extra_data: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Any extra custom key-value pairs received in the payload",
    )

    @property
    def normalized_action(self) -> str:
        """Uppercase normalized action string."""
        return (self.action or "ALERT").strip().upper()

    @property
    def is_bullish(self) -> bool:
        """Check if action indicates a bullish / long signal."""
        return self.normalized_action in ("BUY", "LONG", "BULLISH", "CALL")

    @property
    def is_bearish(self) -> bool:
        """Check if action indicates a bearish / short signal."""
        return self.normalized_action in ("SELL", "SHORT", "BEARISH", "PUT")

    @property
    def embed_color(self) -> int:
        """Hex color code for Discord Embed:
        Green for Bullish (0x00FF88), Red for Bearish (0xFF3366), Blue for Neutral (0x3399FF).
        """
        if self.is_bullish:
            return 0x00FF88
        elif self.is_bearish:
            return 0xFF3366
        return 0x3399FF
