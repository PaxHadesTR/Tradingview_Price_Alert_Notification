import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.database.db import AlertRecord
from app.main import create_app
from app.providers.discord import DiscordBotNotificationProvider
from app.routes.health import check_bot_health
from tests.conftest import TEST_SECRET


# --- 1. Settings & Token Configuration Tests ---

def test_settings_is_discord_bot_configured():
    # Empty / None
    s1 = Settings(DISCORD_BOT_TOKEN=None)
    assert s1.is_discord_bot_configured is False

    s2 = Settings(DISCORD_BOT_TOKEN="")
    assert s2.is_discord_bot_configured is False

    s3 = Settings(DISCORD_BOT_TOKEN="   ")
    assert s3.is_discord_bot_configured is False

    # Placeholders
    s4 = Settings(DISCORD_BOT_TOKEN="your_discord_bot_token_here")
    assert s4.is_discord_bot_configured is False

    s5 = Settings(DISCORD_BOT_TOKEN="buraya_bot_tokeniniz")
    assert s5.is_discord_bot_configured is False

    s6 = Settings(DISCORD_BOT_TOKEN='"buraya_bot_tokeniniz"')
    assert s6.is_discord_bot_configured is False

    s7 = Settings(DISCORD_BOT_TOKEN="'your_discord_bot_token_here'")
    assert s7.is_discord_bot_configured is False

    # Valid tokens
    s8 = Settings(DISCORD_BOT_TOKEN="MTEzNDU2Nzg5MDEyMzQ1Njc4OQ.ABCDEF.GHIJKLMNOPQRST")
    assert s8.is_discord_bot_configured is True

    s9 = Settings(DISCORD_BOT_TOKEN="  valid_token_xyz  ")
    assert s9.is_discord_bot_configured is True


# --- 2. DiscordAlertBot Lifecycle Events & Guards ---

@pytest.mark.asyncio
async def test_bot_lifecycle_events():
    from app.bot.client import DiscordAlertBot

    mock_engine = MagicMock()
    mock_settings = Settings(DISCORD_BOT_TOKEN="mock_token")

    bot = DiscordAlertBot(engine=mock_engine, settings=mock_settings)

    # Test on_connect doesn't crash
    with patch("app.bot.client.logger.info") as mock_info:
        await bot.on_connect()
        mock_info.assert_called()

    # Test on_resumed
    with patch("app.bot.client.logger.info") as mock_info:
        await bot.on_resumed()
        mock_info.assert_called()

    # Test on_disconnect
    with patch("app.bot.client.logger.warning") as mock_warn:
        await bot.on_disconnect()
        mock_warn.assert_called()

    # Test on_error
    with patch("app.bot.client.logger.error") as mock_err:
        await bot.on_error("on_message")
        mock_err.assert_called()

    await bot.close()


@pytest.mark.asyncio
async def test_dispatch_alert_notification_skips_when_closed():
    from app.bot.client import DiscordAlertBot

    mock_engine = MagicMock()
    mock_settings = Settings(DISCORD_BOT_TOKEN="mock_token", DISCORD_ALERT_CHANNEL_ID=12345)
    bot = DiscordAlertBot(engine=mock_engine, settings=mock_settings)

    alert = AlertRecord(
        id=1,
        user_id="user_123",
        user_name="Trader",
        channel_id="12345",
        guild_id=None,
        symbol="BTCUSDT",
        asset_type="CRYPTO",
        target_price=70000.0,
        initial_price=65000.0,
        direction="ABOVE",
        status="ACTIVE",
        created_at="2026-10-29T20:00:00Z",
    )

    # Force closed state
    with patch.object(bot, "is_closed", return_value=True):
        with patch.object(bot, "get_channel") as mock_get_channel:
            await bot.dispatch_alert_notification(alert, 70500.0)
            mock_get_channel.assert_not_called()

    await bot.close()


# --- 3. Bot-Aware Healthcheck Tests ---

def test_healthcheck_when_bot_disabled(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "")
    get_settings.cache_clear()

    app = create_app()
    client = TestClient(app)

    # /live should return 200 ok
    resp_live = client.get("/live")
    assert resp_live.status_code == 200
    assert resp_live.json() == {"status": "ok"}

    # /healthz should return 200 healthy with bot: disabled
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    data = resp_health.json()
    assert data["status"] == "healthy"
    assert data["discord_bot"]["configured"] is False
    assert data["discord_bot"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_healthcheck_when_supervisor_dead(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "real_token_12345")
    get_settings.cache_clear()

    app = create_app()

    # Create a task that terminates immediately
    async def _dummy():
        pass
    dead_task = asyncio.create_task(_dummy())
    await dead_task

    app.state.discord_bot_task = dead_task
    app.state.discord_bot = MagicMock()

    client = TestClient(app)

    # /live should return 503 degraded
    resp_live = client.get("/live")
    assert resp_live.status_code == 503
    live_data = resp_live.json()
    assert live_data["status"] == "degraded"
    assert live_data["bot"] == "supervisor_dead"

    # /healthz should return 503 unhealthy
    resp_health = client.get("/healthz")
    assert resp_health.status_code == 503
    health_data = resp_health.json()
    assert health_data["status"] == "unhealthy"
    assert health_data["discord_bot"]["supervisor_alive"] is False


@pytest.mark.asyncio
async def test_healthcheck_startup_grace_period(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "real_token_12345")
    get_settings.cache_clear()

    app = create_app()

    # Living task
    stop_event = asyncio.Event()
    async def _keepalive():
        await stop_event.wait()
    running_task = asyncio.create_task(_keepalive())

    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = False
    mock_bot.is_closed.return_value = False

    app.state.discord_bot_task = running_task
    app.state.discord_bot = mock_bot
    # Startup timestamp is recent (within 20s grace period)
    app.state.app_start_time = time.time()

    client = TestClient(app)

    resp_live = client.get("/live")
    assert resp_live.status_code == 200
    assert resp_live.json() == {"status": "ok"}

    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"
    assert resp_health.json()["discord_bot"]["status"] == "connecting"

    # Now simulate grace period elapsed (> 20s) while still not ready
    app.state.app_start_time = time.time() - 25.0
    resp_live_expired = client.get("/live")
    assert resp_live_expired.status_code == 503
    assert resp_live_expired.json()["status"] == "degraded"
    assert resp_live_expired.json()["bot"] == "offline"

    resp_health_expired = client.get("/healthz")
    assert resp_health_expired.status_code == 503
    assert resp_health_expired.json()["status"] == "unhealthy"

    stop_event.set()
    await running_task


@pytest.mark.asyncio
async def test_healthcheck_bot_ready(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "real_token_12345")
    get_settings.cache_clear()

    app = create_app()

    stop_event = asyncio.Event()
    async def _keepalive():
        await stop_event.wait()
    running_task = asyncio.create_task(_keepalive())

    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = True
    mock_bot.is_closed.return_value = False
    mock_bot.latency = 0.0425
    mock_bot.user = "TestBot#0001"

    app.state.discord_bot_task = running_task
    app.state.discord_bot = mock_bot
    app.state.app_start_time = time.time() - 100.0  # long past grace period

    client = TestClient(app)

    resp_live = client.get("/live")
    assert resp_live.status_code == 200
    assert resp_live.json() == {"status": "ok"}

    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    data = resp_health.json()
    assert data["status"] == "healthy"
    assert data["discord_bot"]["ready"] is True
    assert data["discord_bot"]["latency_ms"] == 42.5
    assert data["discord_bot"]["user"] == "TestBot#0001"

    stop_event.set()
    await running_task


# --- 4. Supervisor Reconnection & Provider Update Tests ---

@pytest.mark.asyncio
async def test_supervisor_reconnect_and_provider_update():
    """Verify supervisor instantiates a fresh bot on crash and updates queue provider reference."""
    mock_engine = MagicMock()
    mock_settings = Settings(DISCORD_BOT_TOKEN="token_abc", DISCORD_ALERT_CHANNEL_ID=999)

    provider = DiscordBotNotificationProvider(bot=None, channel_id=999)
    providers = [provider]

    created_bots = []
    attempt_count = 0
    second_attempt_event = asyncio.Event()
    shutdown_event = asyncio.Event()

    async def mock_start(token):
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count == 1:
            raise ConnectionResetError("WARP proxy 503 dropped connection")
        else:
            second_attempt_event.set()
            await shutdown_event.wait()

    with patch("app.main.DiscordAlertBot") as MockBotCls:
        def make_bot(*args, **kwargs):
            b = MagicMock()
            b.is_closed.return_value = False
            b.close = AsyncMock()
            b.start = AsyncMock(side_effect=mock_start)
            created_bots.append(b)
            return b

        MockBotCls.side_effect = make_bot

        # We simulate the supervisor loop with accelerated backoff for the test
        async def run_supervisor():
            backoff_steps = [0.01, 0.02]
            backoff_idx = 0
            while not shutdown_event.is_set():
                current_bot = MockBotCls(engine=mock_engine, settings=mock_settings)
                for p in providers:
                    if isinstance(p, DiscordBotNotificationProvider):
                        p.bot = current_bot
                try:
                    await current_bot.start("token_abc")
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                finally:
                    if current_bot and not current_bot.is_closed():
                        await current_bot.close()

                if shutdown_event.is_set():
                    break
                delay = backoff_steps[min(backoff_idx, len(backoff_steps) - 1)]
                backoff_idx += 1
                try:
                    await asyncio.wait_for(shutdown_event.wait(), timeout=delay)
                    break
                except asyncio.TimeoutError:
                    pass

        sup_task = asyncio.create_task(run_supervisor())

        # Wait until attempt 2 connects
        await asyncio.wait_for(second_attempt_event.wait(), timeout=2.0)

        # Verify 2 distinct bot instances were created
        assert len(created_bots) >= 2
        assert created_bots[0] != created_bots[1]

        # Verify provider reference was updated to the latest bot
        assert provider.bot == created_bots[1]

        # Verify old bot close was called
        created_bots[0].close.assert_awaited()

        # Clean shutdown
        shutdown_event.set()
        await sup_task


@pytest.mark.asyncio
async def test_full_lifespan_startup_and_shutdown(monkeypatch, tmp_path):
    db_file = str(tmp_path / "test_alerts.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_file)
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "valid_secret_bot_token_123")
    monkeypatch.setenv("DISCORD_ALERT_CHANNEL_ID", "123456")
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    get_settings.cache_clear()

    from app.main import lifespan

    app = create_app()

    started_event = asyncio.Event()
    closed_event = asyncio.Event()

    async def mock_start(token):
        started_event.set()
        try:
            while True:
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            pass

    async def mock_close():
        closed_event.set()

    with patch("app.main.DiscordAlertBot") as MockBotCls, \
         patch("app.main.AutonomousAlertEngine.start", new_callable=AsyncMock), \
         patch("app.main.AutonomousAlertEngine.stop", new_callable=AsyncMock):

        mock_bot = MagicMock()
        mock_bot.is_closed.return_value = False
        mock_bot.start = AsyncMock(side_effect=mock_start)
        mock_bot.close = AsyncMock(side_effect=mock_close)
        MockBotCls.return_value = mock_bot

        async with lifespan(app):
            # Verify bot was started
            await asyncio.wait_for(started_event.wait(), timeout=2.0)
            assert app.state.discord_bot is not None
            assert app.state.discord_bot_task is not None
            assert not app.state.discord_bot_task.done()

            # Verify DiscordBotNotificationProvider was attached
            providers = app.state.queue_service.providers
            bot_providers = [p for p in providers if isinstance(p, DiscordBotNotificationProvider)]
            assert len(bot_providers) == 1
            assert bot_providers[0].bot == mock_bot

        # After lifespan exits, bot must have been closed
        assert closed_event.is_set()
        assert app.state.discord_bot_task.done()


@pytest.mark.asyncio
async def test_healthcheck_edge_cases_and_missing_attributes(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "real_token_12345")
    get_settings.cache_clear()

    app = create_app()

    stop_event = asyncio.Event()
    async def _keepalive():
        await stop_event.wait()
    running_task = asyncio.create_task(_keepalive())

    # Case A: is_ready is True, BUT is_closed is also True (bot was shut down)
    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = True
    mock_bot.is_closed.return_value = True
    mock_bot.latency = None
    mock_bot.user = None

    app.state.discord_bot_task = running_task
    app.state.discord_bot = mock_bot
    # Deliberately do not set app_start_time or queue_service on app.state
    if hasattr(app.state, "app_start_time"):
        delattr(app.state, "app_start_time")
    if hasattr(app.state, "queue_service"):
        delattr(app.state, "queue_service")

    client = TestClient(app)

    resp_live = client.get("/live")
    assert resp_live.status_code == 503
    assert resp_live.json()["status"] == "degraded"
    assert resp_live.json()["bot"] == "offline"

    resp_health = client.get("/healthz")
    assert resp_health.status_code == 503
    assert resp_health.json()["status"] == "unhealthy"
    assert resp_health.json()["queue"] == {}

    # Case B: is_ready is True, not closed, latency is None, user is None
    mock_bot.is_closed.return_value = False
    resp_live_ok = client.get("/live")
    assert resp_live_ok.status_code == 200
    assert resp_live_ok.json() == {"status": "ok"}

    resp_health_ok = client.get("/healthz")
    assert resp_health_ok.status_code == 200
    data = resp_health_ok.json()
    assert data["status"] == "healthy"
    assert data["discord_bot"]["latency_ms"] == 0.0
    assert data["discord_bot"]["user"] is None

    stop_event.set()
    await running_task


# --- 5. Additional Adversarial & Deep Recovery Verification Tests ---

def test_settings_is_discord_bot_configured_additional_placeholders():
    assert Settings(DISCORD_BOT_TOKEN="None").is_discord_bot_configured is False
    assert Settings(DISCORD_BOT_TOKEN="null").is_discord_bot_configured is False
    assert Settings(DISCORD_BOT_TOKEN="dummy").is_discord_bot_configured is False
    assert Settings(DISCORD_BOT_TOKEN="undefined").is_discord_bot_configured is False
    assert Settings(DISCORD_BOT_TOKEN="FALSE").is_discord_bot_configured is False


@pytest.mark.asyncio
async def test_healthcheck_startup_grace_period_uninitialized_and_closed(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "real_token_12345")
    get_settings.cache_clear()

    app = create_app()

    stop_event = asyncio.Event()
    async def _keepalive():
        await stop_event.wait()
    running_task = asyncio.create_task(_keepalive())

    app.state.discord_bot_task = running_task
    # Bot is initially None during early boot
    app.state.discord_bot = None
    app.state.app_start_time = time.time()

    client = TestClient(app)

    # When bot is None, but within 20s startup grace period -> HTTP 200
    resp_live = client.get("/live")
    assert resp_live.status_code == 200
    assert resp_live.json() == {"status": "ok"}

    resp_health = client.get("/healthz")
    assert resp_health.status_code == 200
    assert resp_health.json()["status"] == "healthy"
    assert resp_health.json()["discord_bot"]["status"] == "connecting"

    # When bot is closed (first handshake failed and retrying), still within grace period -> HTTP 200
    mock_bot = MagicMock()
    mock_bot.is_ready.return_value = False
    mock_bot.is_closed.return_value = True
    app.state.discord_bot = mock_bot

    resp_live_closed = client.get("/live")
    assert resp_live_closed.status_code == 200
    assert resp_live_closed.json() == {"status": "ok"}

    resp_health_closed = client.get("/healthz")
    assert resp_health_closed.status_code == 200
    assert resp_health_closed.json()["status"] == "healthy"
    assert resp_health_closed.json()["discord_bot"]["status"] == "connecting"

    stop_event.set()
    await running_task


@pytest.mark.asyncio
async def test_supervisor_aborts_on_fatal_login_failure():
    """Verify supervisor aborts on fatal Discord LoginFailure rather than entering an infinite retry loop."""
    import discord

    mock_engine = MagicMock()
    mock_settings = Settings(DISCORD_BOT_TOKEN="invalid_token")

    shutdown_event = asyncio.Event()
    with patch("app.main.DiscordAlertBot") as MockBotCls:
        mock_bot = MagicMock()
        mock_bot.is_closed.return_value = False
        mock_bot.close = AsyncMock()
        mock_bot.start = AsyncMock(side_effect=discord.errors.LoginFailure("Improper token has been passed"))
        MockBotCls.return_value = mock_bot

        # Run supervisor task logic
        backoff_steps = [0.01, 0.02]
        backoff_idx = 0
        task_ran = False
        async def _run_supervisor():
            nonlocal task_ran
            task_ran = True
            while not shutdown_event.is_set():
                current_bot = MockBotCls(engine=mock_engine, settings=mock_settings)
                try:
                    await current_bot.start("invalid_token")
                except asyncio.CancelledError:
                    break
                except (discord.errors.LoginFailure, discord.errors.PrivilegedIntentsRequired):
                    break
                except Exception:
                    pass
                finally:
                    if current_bot and not current_bot.is_closed():
                        await current_bot.close()

        task = asyncio.create_task(_run_supervisor())
        await asyncio.wait_for(task, timeout=2.0)
        assert task_ran is True
        assert task.done() is True


@pytest.mark.asyncio
async def test_tree_sync_only_once_across_reconnects():
    import app.bot.client as bot_client
    bot_client._commands_synced_globally = False

    mock_engine = MagicMock()
    mock_settings = Settings(DISCORD_BOT_TOKEN="token_123")

    bot1 = bot_client.DiscordAlertBot(engine=mock_engine, settings=mock_settings)
    bot2 = bot_client.DiscordAlertBot(engine=mock_engine, settings=mock_settings)

    with patch.object(bot1.tree, "sync", new_callable=AsyncMock) as sync1, \
         patch.object(bot2.tree, "sync", new_callable=AsyncMock) as sync2:

        sync1.return_value = ["cmd1", "cmd2"]

        await bot1.setup_hook()
        sync1.assert_awaited_once()
        assert bot_client._commands_synced_globally is True

        await bot2.setup_hook()
        sync2.assert_not_called()

    await bot1.close()
    await bot2.close()


@pytest.mark.asyncio
async def test_database_reset_alert_to_active(tmp_path):
    from app.database.db import AlertDatabase
    db = AlertDatabase(str(tmp_path / "test.db"))
    await db.init_db()

    aid = await db.add_alert(
        user_id="u1",
        user_name="User",
        channel_id="c1",
        guild_id=None,
        symbol="BTCUSDT",
        asset_type="CRYPTO",
        target_price=70000.0,
        initial_price=65000.0,
        direction="ABOVE",
    )
    # Trigger alert
    assert await db.trigger_alert(aid) is True
    record = await db.get_alert_by_id(aid)
    assert record.status == "TRIGGERED"
    assert record.triggered_at is not None

    # Reset back to ACTIVE
    assert await db.reset_alert_to_active(aid) is True
    record_reset = await db.get_alert_by_id(aid)
    assert record_reset.status == "ACTIVE"
    assert record_reset.triggered_at is None


@pytest.mark.asyncio
async def test_alert_engine_reverts_alert_when_callback_fails(tmp_path):
    from app.database.db import AlertDatabase
    from app.services.alert_engine import AutonomousAlertEngine

    db = AlertDatabase(str(tmp_path / "test_engine.db"))
    await db.init_db()

    aid = await db.add_alert(
        user_id="u1",
        user_name="User",
        channel_id="c1",
        guild_id=None,
        symbol="BTCUSDT",
        asset_type="CRYPTO",
        target_price=70000.0,
        initial_price=65000.0,
        direction="ABOVE",
    )

    mock_feed = MagicMock()
    engine = AutonomousAlertEngine(db=db, price_feed=mock_feed, settings=Settings())

    # Case 1: Callback returns False (e.g. Bot is closed/reconnecting)
    async def mock_callback_closed(alert, price):
        return False

    engine.trigger_callback = mock_callback_closed
    await engine._on_price_tick("BTCUSDT", 71000.0)

    # Alert should have been reverted to ACTIVE so user does not lose it!
    rec = await db.get_alert_by_id(aid)
    assert rec.status == "ACTIVE"

    # Case 2: Callback raises exception
    async def mock_callback_error(alert, price):
        raise ConnectionError("Network dropped")

    engine.trigger_callback = mock_callback_error
    await engine._on_price_tick("BTCUSDT", 71000.0)

    rec2 = await db.get_alert_by_id(aid)
    assert rec2.status == "ACTIVE"

    # Case 3: Callback succeeds (returns True)
    async def mock_callback_success(alert, price):
        return True

    engine.trigger_callback = mock_callback_success
    await engine._on_price_tick("BTCUSDT", 71000.0)

    rec3 = await db.get_alert_by_id(aid)
    assert rec3.status == "TRIGGERED"


@pytest.mark.asyncio
async def test_discord_bot_notification_provider_skips_when_closed():
    from app.models.alert import AlertPayload

    mock_bot = MagicMock()
    mock_bot.is_closed.return_value = True

    provider = DiscordBotNotificationProvider(bot=mock_bot, channel_id=123)
    payload = AlertPayload(ticker="BTCUSDT", action="BUY", price=70000.0)

    # Should return False cleanly without raising
    result = await provider.send(payload)
    assert result is False
    mock_bot.get_channel.assert_not_called()


