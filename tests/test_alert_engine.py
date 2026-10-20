import pytest
import pytest_asyncio
from app.config import Settings
from app.database.db import AlertDatabase, AlertRecord
from app.market_data.feed import UnifiedPriceFeed
from app.services.alert_engine import AutonomousAlertEngine


class DummyMarketFeed(UnifiedPriceFeed):
    def __init__(self):
        super().__init__()
        self.mock_prices = {
            "BTCUSDT": 65000.0,
            "THYAO.IS": 300.0,
        }

    async def get_current_price(self, raw_symbol: str):
        from app.market_data.symbols import classify_and_normalize
        norm, _ = classify_and_normalize(raw_symbol)
        return self.mock_prices.get(norm, 100.0)


@pytest_asyncio.fixture
async def setup_engine(tmp_path):
    db_file = str(tmp_path / "test_engine.db")
    db = AlertDatabase(db_path=db_file)
    await db.init_db()

    feed = DummyMarketFeed()
    settings = Settings(MAX_ACTIVE_ALERTS=5, ALERT_EXPIRY_DAYS=30)

    triggered_alerts = []

    async def on_trigger(alert: AlertRecord, current_price: float):
        triggered_alerts.append((alert, current_price))

    engine = AutonomousAlertEngine(
        db=db,
        price_feed=feed,
        settings=settings,
        trigger_callback=on_trigger,
    )

    return engine, triggered_alerts, feed


@pytest.mark.asyncio
async def test_create_alert_direction_above(setup_engine):
    engine, triggered, feed = setup_engine

    # Current BTC price is 65000, target is 68000 -> direction should be ABOVE
    success, msg, record = await engine.create_user_alert(
        user_id="u1",
        user_name="Pax",
        channel_id="c1",
        guild_id="g1",
        raw_symbol="btcusdt",
        target_price=68000.0,
    )
    assert success is True
    assert record is not None
    assert record.symbol == "BTCUSDT"
    assert record.direction == "ABOVE"
    assert record.initial_price == 65000.0


@pytest.mark.asyncio
async def test_create_alert_direction_below(setup_engine):
    engine, triggered, feed = setup_engine

    # Current BTC price is 65000, target is 60000 -> direction should be BELOW
    success, msg, record = await engine.create_user_alert(
        user_id="u1",
        user_name="Pax",
        channel_id="c1",
        guild_id="g1",
        raw_symbol="btcusdt",
        target_price=60000.0,
    )
    assert success is True
    assert record.direction == "BELOW"


@pytest.mark.asyncio
async def test_alert_quota_enforcement(setup_engine):
    engine, triggered, feed = setup_engine
    # Max alerts set to 5 in fixture
    for i in range(5):
        s, m, r = await engine.create_user_alert(
            user_id="u1", user_name="Pax", channel_id="c1", guild_id="g1",
            raw_symbol="btcusdt", target_price=70000.0 + i,
        )
        assert s is True

    # 6th should be rejected
    s, m, r = await engine.create_user_alert(
        user_id="u1", user_name="Pax", channel_id="c1", guild_id="g1",
        raw_symbol="btcusdt", target_price=80000.0,
    )
    assert s is False
    assert "kotası dolu" in m


@pytest.mark.asyncio
async def test_price_tick_triggers_alert(setup_engine):
    engine, triggered, feed = setup_engine

    # Create ABOVE alert at 68000
    await engine.create_user_alert(
        user_id="u1", user_name="Pax", channel_id="c1", guild_id="g1",
        raw_symbol="btcusdt", target_price=68000.0,
    )

    # Tick at 67000: should NOT trigger
    await engine._on_price_tick("BTCUSDT", 67000.0)
    assert len(triggered) == 0

    # Tick at 68500: should trigger!
    await engine._on_price_tick("BTCUSDT", 68500.0)
    assert len(triggered) == 1
    rec, price = triggered[0]
    assert rec.symbol == "BTCUSDT"
    assert price == 68500.0

    # Another tick should not re-trigger because it's already TRIGGERED in DB
    await engine._on_price_tick("BTCUSDT", 69000.0)
    assert len(triggered) == 1
