from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Security: Secret token required for TradingView Webhooks
    WEBHOOK_SECRET: str = "change_me_in_production"

    # Discord Webhook Configuration (for TradingView direct forwarding)
    DISCORD_WEBHOOK_URL: Optional[str] = None
    DISCORD_BOT_USERNAME: str = "TradingView Alert"
    DISCORD_AVATAR_URL: Optional[str] = "https://upload.wikimedia.org/wikipedia/commons/e/e4/TradingView_Logo.svg"

    # Discord Bot Configuration (for interactive Slash Commands and autonomous alerts)
    DISCORD_BOT_TOKEN: Optional[str] = None
    DISCORD_ALERT_CHANNEL_ID: Optional[int] = None
    # Optional HTTP/SOCKS5 proxy for connecting to Discord from blocked regions (e.g. Turkey)
    DISCORD_PROXY: Optional[str] = None

    # Autonomous Alert Engine & Limits
    SQLITE_DB_PATH: str = "./data/alerts.db"
    MAX_ACTIVE_ALERTS: int = 100
    ALERT_EXPIRY_DAYS: int = 180
    YAHOO_POLL_INTERVAL_SECONDS: float = 20.0
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"

    # Rate Limiting & Queue Settings
    RATE_LIMIT_PER_SECOND: float = 2.0
    MAX_QUEUE_CAPACITY: int = 500
    HTTP_TIMEOUT_SECONDS: float = 10.0


@lru_cache()
def get_settings() -> Settings:
    """Return cached singleton instance of Settings."""
    return Settings()
