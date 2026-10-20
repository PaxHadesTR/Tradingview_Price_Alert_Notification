import asyncio
import logging
from typing import Callable, Coroutine, List, Optional, Tuple
from app.config import Settings
from app.database.db import AlertDatabase, AlertRecord
from app.market_data.feed import UnifiedPriceFeed
from app.market_data.symbols import classify_and_normalize

logger = logging.getLogger(__name__)

AlertTriggerCallback = Callable[[AlertRecord, float], Coroutine[None, None, None]]


class AutonomousAlertEngine:
    """Core autonomous alert manager matching live prices against database alerts and enforcing quotas."""

    def __init__(
        self,
        db: AlertDatabase,
        price_feed: UnifiedPriceFeed,
        settings: Settings,
        trigger_callback: Optional[AlertTriggerCallback] = None,
    ) -> None:
        self.db = db
        self.feed = price_feed
        self.settings = settings
        self.trigger_callback = trigger_callback
        self._running = False
        self._expiry_task: Optional[asyncio.Task] = None

        # Wire price feed to evaluate alerts
        self.feed.add_listener(self._on_price_tick)
        self.feed.set_active_equity_supplier(self._get_active_non_crypto_symbols)

    async def _get_active_non_crypto_symbols(self) -> List[str]:
        """Fetch all active non-crypto symbols currently registered in database for Yahoo polling."""
        active = await self.db.get_active_alerts()
        return [a.symbol for a in active if a.asset_type == "EQUITY_FOREX"]

    async def _on_price_tick(self, symbol: str, current_price: float) -> None:
        """Evaluate active alerts when a price tick arrives."""
        active_alerts = await self.db.get_active_alerts(symbol=symbol)
        if not active_alerts:
            return

        for alert in active_alerts:
            should_trigger = False

            if alert.direction == "ABOVE" and current_price >= alert.target_price:
                should_trigger = True
            elif alert.direction == "BELOW" and current_price <= alert.target_price:
                should_trigger = True

            if should_trigger:
                # Atomically mark triggered in DB to prevent duplicate fires
                success = await self.db.trigger_alert(alert.id)
                if success:
                    logger.info(
                        "Alert #%d triggered! %s %s target %.4f reached at %.4f",
                        alert.id, alert.symbol, alert.direction, alert.target_price, current_price,
                    )
                    if self.trigger_callback:
                        try:
                            await self.trigger_callback(alert, current_price)
                        except Exception as e:
                            logger.error("Error executing alert trigger callback: %s", e, exc_info=True)

    async def create_user_alert(
        self,
        user_id: str,
        user_name: str,
        channel_id: str,
        guild_id: Optional[str],
        raw_symbol: str,
        target_price: float,
        note: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[AlertRecord]]:
        """Validate quotas, fetch current price, detect direction, and register alert."""
        # 1. Enforce max active alerts quota
        total_active = await self.db.count_active_alerts()
        if total_active >= self.settings.MAX_ACTIVE_ALERTS:
            return (
                False,
                f"Sistem alarm kotası dolu! (Aktif: {total_active}/{self.settings.MAX_ACTIVE_ALERTS}). Lütfen eski alarmları temizleyin.",
                None,
            )

        # 2. Normalize symbol and classify asset type
        symbol, asset_type = classify_and_normalize(raw_symbol)

        # 3. Retrieve current market price
        current_price = await self.feed.get_current_price(symbol)
        if current_price is None:
            return (
                False,
                f"**{symbol}** sembolü için anlık fiyat alınamadı. Lütfen sembol adını kontrol edin (örn: BTCUSDT, THYAO, USDTRY, AAPL).",
                None,
            )

        # 4. Auto-detect direction
        if target_price > current_price:
            direction = "ABOVE"
        elif target_price < current_price:
            direction = "BELOW"
        else:
            return (
                False,
                f"Hedef fiyat (${target_price:,.4f}) şu anki piyasa fiyatına (${current_price:,.4f}) zaten eşit!",
                None,
            )

        # 5. Insert alert into database
        alert_id = await self.db.add_alert(
            user_id=user_id,
            user_name=user_name,
            channel_id=channel_id,
            guild_id=guild_id,
            symbol=symbol,
            asset_type=asset_type,
            target_price=target_price,
            initial_price=current_price,
            direction=direction,
            note=note,
        )

        record = await self.db.get_alert_by_id(alert_id)
        return True, "Alarm başarıyla oluşturuldu.", record

    async def start(self) -> None:
        """Start database, price feed, and expiration cleaner."""
        if self._running:
            return
        self._running = True
        await self.db.init_db()
        self.feed.start()
        self._expiry_task = asyncio.create_task(self._expiry_worker(), name="alert_expiry_cleaner")
        logger.info("AutonomousAlertEngine started.")

    async def stop(self) -> None:
        """Gracefully stop background engines."""
        self._running = False
        if self._expiry_task:
            self._expiry_task.cancel()
            try:
                await self._expiry_task
            except asyncio.CancelledError:
                pass
            self._expiry_task = None
        await self.feed.stop()
        logger.info("AutonomousAlertEngine stopped.")

    async def _expiry_worker(self) -> None:
        """Periodically clean up stale alerts older than ALERT_EXPIRY_DAYS."""
        while self._running:
            try:
                await asyncio.sleep(3600)  # Check every hour
                await self.db.expire_stale_alerts(self.settings.ALERT_EXPIRY_DAYS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in alert expiry worker: %s", e, exc_info=True)
