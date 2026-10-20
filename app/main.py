import asyncio
import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.bot.client import DiscordAlertBot
from app.config import get_settings
from app.database.db import AlertDatabase
from app.market_data.feed import UnifiedPriceFeed
from app.providers.base import BaseNotificationProvider
from app.providers.discord import DiscordWebhookProvider
from app.routes.health import router as health_router
from app.routes.webhook import router as webhook_router
from app.services.alert_engine import AutonomousAlertEngine
from app.services.queue import AlertQueueService
from app.services.rate_limiter import AsyncTokenBucket

settings = get_settings()

logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tradingview_alerts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager initializing both webhook queue and autonomous alert bot."""
    logger.info("Initializing Autonomous Price Alert & Discord Bot Service...")

    # 1. Initialize Webhook Queue Infrastructure (TradingView Forwarding)
    providers: List[BaseNotificationProvider] = []
    if settings.DISCORD_WEBHOOK_URL:
        discord_provider = DiscordWebhookProvider(
            webhook_url=settings.DISCORD_WEBHOOK_URL,
            bot_username=settings.DISCORD_BOT_USERNAME,
            avatar_url=settings.DISCORD_AVATAR_URL,
            timeout_seconds=settings.HTTP_TIMEOUT_SECONDS,
        )
        providers.append(discord_provider)

    rate_limiter = AsyncTokenBucket(rate=settings.RATE_LIMIT_PER_SECOND)
    queue_service = AlertQueueService(
        providers=providers,
        rate_limiter=rate_limiter,
        max_capacity=settings.MAX_QUEUE_CAPACITY,
    )
    queue_service.start()
    app.state.queue_service = queue_service

    # 2. Initialize Autonomous Market Engine & SQLite Storage
    db = AlertDatabase(db_path=settings.SQLITE_DB_PATH)
    price_feed = UnifiedPriceFeed()
    alert_engine = AutonomousAlertEngine(
        db=db,
        price_feed=price_feed,
        settings=settings,
    )
    await alert_engine.start()
    app.state.alert_engine = alert_engine

    # 3. Initialize Discord Bot (if token provided)
    bot: Optional[DiscordAlertBot] = None
    bot_task: Optional[asyncio.Task] = None

    if settings.DISCORD_BOT_TOKEN and settings.DISCORD_BOT_TOKEN != "your_discord_bot_token_here":
        bot = DiscordAlertBot(engine=alert_engine, settings=settings)
        bot_task = asyncio.create_task(bot.start(settings.DISCORD_BOT_TOKEN), name="discord_bot_gateway")
        app.state.discord_bot = bot
        logger.info("Discord Bot client scheduled for connection to Discord Gateway.")
    else:
        logger.info("No DISCORD_BOT_TOKEN configured. Discord Slash Commands Bot is idle. Webhook & Market APIs active.")

    yield

    logger.info("Shutting down background services...")
    if bot:
        try:
            await bot.close()
        except Exception as e:
            logger.warning("Error closing Discord bot: %s", e)
    if bot_task:
        bot_task.cancel()

    await alert_engine.stop()
    await queue_service.stop()
    logger.info("All background engines safely terminated.")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    application = FastAPI(
        title="Autonomous Price Alert & Discord Bot API",
        description="Unified market price monitor, TradingView webhook ingestion, and interactive Discord bot.",
        version="2.0.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(webhook_router)

    return application


app = create_app()
