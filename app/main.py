import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import discord
from app.bot.client import DiscordAlertBot
from app.config import get_settings
from app.database.db import AlertDatabase
from app.market_data.feed import UnifiedPriceFeed
from app.providers.base import BaseNotificationProvider
from app.providers.discord import DiscordBotNotificationProvider, DiscordWebhookProvider
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
logging.getLogger("discord").setLevel(logging.INFO)
logging.getLogger("discord.gateway").setLevel(logging.INFO)
logging.getLogger("discord.client").setLevel(logging.INFO)
logger = logging.getLogger("tradingview_alerts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager initializing both webhook queue and autonomous alert bot."""
    settings = get_settings()
    logger.info("Initializing Autonomous Price Alert & Discord Bot Service...")
    app.state.app_start_time = time.time()

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

    # 3. Initialize Discord Bot with Resilient Supervisor Loop
    bot_task: Optional[asyncio.Task] = None
    shutdown_event = asyncio.Event()

    token = (settings.DISCORD_BOT_TOKEN or "").strip().strip('"').strip("'")
    if settings.is_discord_bot_configured:
        # If no separate DISCORD_WEBHOOK_URL was configured, use the active Discord Bot to dispatch TradingView alerts!
        if not settings.DISCORD_WEBHOOK_URL and settings.DISCORD_ALERT_CHANNEL_ID:
            bot_provider = DiscordBotNotificationProvider(
                bot=None,
                channel_id=settings.DISCORD_ALERT_CHANNEL_ID,
            )
            queue_service.providers.append(bot_provider)
            logger.info(
                "Attached Discord Bot provider to TradingView Webhook Queue (Target Channel: %s)",
                settings.DISCORD_ALERT_CHANNEL_ID,
            )

        async def _run_bot_supervisor():
            backoff_steps = [5.0, 10.0, 30.0, 60.0]
            backoff_idx = 0

            while not shutdown_event.is_set():
                current_bot: Optional[DiscordAlertBot] = None
                connect_start = time.time()
                try:
                    logger.info("Supervisor: Instantiating fresh DiscordAlertBot client...")
                    current_bot = DiscordAlertBot(engine=alert_engine, settings=settings)
                    app.state.discord_bot = current_bot

                    # Atomically update bot instance in queue providers
                    for provider in queue_service.providers:
                        if isinstance(provider, DiscordBotNotificationProvider):
                            provider.bot = current_bot

                    logger.info("Supervisor: Connecting Discord Bot to Discord Gateway...")
                    await current_bot.start(token)
                    logger.warning("Supervisor: Discord Bot gateway session ended normally.")
                except asyncio.CancelledError:
                    logger.info("Supervisor: Discord Bot supervisor task cancelled.")
                    break
                except (discord.errors.LoginFailure, discord.errors.PrivilegedIntentsRequired) as fatal_err:
                    logger.critical(
                        "Supervisor: FATAL Discord authentication/permission error: %s. Aborting supervisor to prevent API bans.",
                        fatal_err,
                    )
                    break
                except Exception as bot_err:
                    logger.error("Supervisor: Discord Bot gateway session terminated with error: %s", bot_err, exc_info=True)
                finally:
                    if current_bot and not current_bot.is_closed():
                        try:
                            await current_bot.close()
                        except Exception as close_err:
                            logger.debug("Supervisor: Error closing bot client: %s", close_err)

                if shutdown_event.is_set():
                    break

                # If connection lasted > 60s, reset backoff progression
                if time.time() - connect_start > 60.0:
                    backoff_idx = 0

                delay = backoff_steps[min(backoff_idx, len(backoff_steps) - 1)]
                backoff_idx += 1

                logger.warning(
                    "Supervisor: Discord Bot disconnected. Attempting reconnection in %.0fs (step %d/%d)...",
                    delay,
                    backoff_idx,
                    len(backoff_steps),
                )
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
                    break
                except asyncio.TimeoutError:
                    pass

        bot_task = asyncio.create_task(_run_bot_supervisor(), name="discord_bot_supervisor")
        app.state.discord_bot_task = bot_task
    else:
        app.state.discord_bot = None
        app.state.discord_bot_task = None
        logger.warning(
            "DISCORD_BOT_TOKEN is empty or placeholder ('%s'). Bot cannot connect to Discord! "
            "Please configure DISCORD_BOT_TOKEN in Coolify Environment Variables and Restart.",
            token[:10] if token else "EMPTY"
        )

    yield

    logger.info("Shutting down background services...")
    shutdown_event.set()

    current_bot = getattr(app.state, "discord_bot", None)
    if current_bot and not current_bot.is_closed():
        try:
            await current_bot.close()
        except Exception as e:
            logger.warning("Error closing Discord bot: %s", e)

    if bot_task and not bot_task.done():
        try:
            await asyncio.wait_for(bot_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
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
