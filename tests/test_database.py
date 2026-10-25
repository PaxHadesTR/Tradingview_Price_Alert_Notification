import os
import pytest
import pytest_asyncio
from app.database.db import AlertDatabase


@pytest_asyncio.fixture
async def temp_db(tmp_path):
    db_file = str(tmp_path / "test_alerts.db")
    database = AlertDatabase(db_path=db_file)
    await database.init_db()
    return database


@pytest.mark.asyncio
async def test_database_crud(temp_db: AlertDatabase):
    # 1. Insert alert
    alert_id = await temp_db.add_alert(
        user_id="user_123",
        user_name="PaxHades",
        channel_id="chan_456",
        guild_id="guild_789",
        symbol="BTCUSDT",
        asset_type="CRYPTO",
        target_price=70000.0,
        initial_price=65000.0,
        direction="ABOVE",
        note="Bull run test",
    )
    assert alert_id is not None
    assert alert_id >= 1

    # 2. Get active alerts
    active = await temp_db.get_active_alerts("BTCUSDT")
    assert len(active) == 1
    record = active[0]
    assert record.symbol == "BTCUSDT"
    assert record.target_price == 70000.0
    assert record.direction == "ABOVE"
    assert record.status == "ACTIVE"

    # 3. Count active alerts
    count = await temp_db.count_active_alerts()
    assert count == 1

    # 4. Trigger alert
    success = await temp_db.trigger_alert(alert_id)
    assert success is True

    # After trigger, active alerts query should be empty
    active_after = await temp_db.get_active_alerts("BTCUSDT")
    assert len(active_after) == 0

    # User alerts list should show status TRIGGERED
    user_alerts = await temp_db.get_user_alerts("user_123")
    assert len(user_alerts) == 1
    assert user_alerts[0].status == "TRIGGERED"
    assert user_alerts[0].triggered_at is not None


@pytest.mark.asyncio
async def test_cancel_alert(temp_db: AlertDatabase):
    alert_id = await temp_db.add_alert(
        user_id="user_123",
        user_name="PaxHades",
        channel_id="chan_456",
        guild_id="guild_789",
        symbol="THYAO.IS",
        asset_type="EQUITY_FOREX",
        target_price=350.0,
        initial_price=310.0,
        direction="ABOVE",
    )
    cancelled = await temp_db.cancel_alert(alert_id=alert_id, user_id="user_123")
    assert cancelled is True

    cancelled_wrong_user = await temp_db.cancel_alert(alert_id=alert_id, user_id="other_user")
    assert cancelled_wrong_user is False


@pytest.mark.asyncio
async def test_notify_dm_persistence(temp_db: AlertDatabase):
    alert_id = await temp_db.add_alert(
        user_id="user_123",
        user_name="Pax",
        channel_id="c1",
        guild_id="g1",
        symbol="BTCUSDT",
        asset_type="CRYPTO",
        target_price=80000.0,
        initial_price=70000.0,
        direction="ABOVE",
        notify_dm=True,
    )
    record = await temp_db.get_alert_by_id(alert_id)
    assert record is not None
    assert record.notify_dm is True


@pytest.mark.asyncio
async def test_watchlist_crud(temp_db: AlertDatabase):
    # Add items
    res1 = await temp_db.add_to_watchlist("user_1", "BTCUSDT", "CRYPTO")
    res2 = await temp_db.add_to_watchlist("user_1", "THYAO.IS", "EQUITY_FOREX")
    assert res1 is True
    assert res2 is True

    # Duplicate should return False
    dup = await temp_db.add_to_watchlist("user_1", "BTCUSDT", "CRYPTO")
    assert dup is False

    # Get user watchlist
    watchlist = await temp_db.get_user_watchlist("user_1")
    assert len(watchlist) == 2
    assert "BTCUSDT" in watchlist
    assert "THYAO.IS" in watchlist

    # Remove item
    removed = await temp_db.remove_from_watchlist("user_1", "BTCUSDT")
    assert removed is True
    updated = await temp_db.get_user_watchlist("user_1")
    assert len(updated) == 1
    assert "BTCUSDT" not in updated


@pytest.mark.asyncio
async def test_clear_alerts_and_stats(temp_db: AlertDatabase):
    # Setup multiple alerts
    a1 = await temp_db.add_alert(
        user_id="u_test", user_name="User", channel_id="c1", guild_id="g1",
        symbol="BTCUSDT", asset_type="CRYPTO", target_price=70000, initial_price=65000, direction="ABOVE",
    )
    a2 = await temp_db.add_alert(
        user_id="u_test", user_name="User", channel_id="c1", guild_id="g1",
        symbol="ETHUSDT", asset_type="CRYPTO", target_price=4000, initial_price=3500, direction="ABOVE",
    )
    # Trigger a1
    await temp_db.trigger_alert(a1)

    # Database stats check
    stats = await temp_db.get_database_stats()
    assert stats["total_alerts"] >= 2
    assert stats["active_alerts"] >= 1
    assert stats["triggered_alerts"] >= 1

    # Clear TRIGGERED
    cleared = await temp_db.clear_user_alerts(user_id="u_test", status="TRIGGERED")
    assert cleared == 1

    # Only ACTIVE (a2) remains
    remaining = await temp_db.get_user_alerts(user_id="u_test")
    assert len(remaining) == 1
    assert remaining[0].id == a2

    # Clear ALL
    cleared_all = await temp_db.clear_user_alerts(user_id="u_test", status="ALL")
    assert cleared_all == 1

    # User alerts now 0
    assert len(await temp_db.get_user_alerts(user_id="u_test")) == 0


@pytest.mark.asyncio
async def test_get_all_watchlist_symbols(temp_db: AlertDatabase):
    await temp_db.add_to_watchlist("user_a", "THYAO.IS", "EQUITY_FOREX")
    await temp_db.add_to_watchlist("user_b", "THYAO.IS", "EQUITY_FOREX")
    await temp_db.add_to_watchlist("user_b", "GOLD", "EQUITY_FOREX")
    await temp_db.add_to_watchlist("user_c", "BTCUSDT", "CRYPTO")

    all_equities = await temp_db.get_all_watchlist_symbols(asset_type="EQUITY_FOREX")
    assert len(all_equities) == 2
    assert "THYAO.IS" in all_equities
    assert "GOLD" in all_equities
    assert "BTCUSDT" not in all_equities
