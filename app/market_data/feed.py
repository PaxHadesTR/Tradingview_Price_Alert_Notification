import asyncio
import logging
import time
from typing import Callable, Coroutine, Dict, List, Optional, Tuple
from app.market_data.binance import BinanceMarketFeed
from app.market_data.symbols import classify_and_normalize
from app.market_data.yahoo import YahooFinanceFeed

logger = logging.getLogger(__name__)

PriceListener = Callable[[str, float], Coroutine[None, None, None]]


class UnifiedPriceFeed:
    """Unified hybrid market feed combining real-time Binance WebSocket and Yahoo Finance Poller."""

    def __init__(
        self,
        binance_feed: Optional[BinanceMarketFeed] = None,
        yahoo_feed: Optional[YahooFinanceFeed] = None,
        cache_ttl_seconds: float = 20.0,
    ) -> None:
        self.binance = binance_feed or BinanceMarketFeed()
        self.yahoo = yahoo_feed or YahooFinanceFeed()
        self.cache_ttl = cache_ttl_seconds
        # Maps symbol -> (price: float, timestamp: float)
        self.price_cache: Dict[str, Tuple[float, float]] = {}
        self._listeners: List[PriceListener] = []
        self._active_non_crypto_supplier: Optional[Callable[[], Coroutine[None, None, List[str]]]] = None

    def set_active_equity_supplier(self, supplier: Callable[[], Coroutine[None, None, List[str]]]) -> None:
        """Provide callback to supply active non-crypto symbols for Yahoo polling."""
        self._active_non_crypto_supplier = supplier

    def add_listener(self, listener: PriceListener) -> None:
        """Register a callback to be invoked on every incoming price update."""
        self._listeners.append(listener)

    async def get_current_price(self, raw_symbol: str) -> Optional[float]:
        """Fetch current price for any symbol, consulting cache first, then live snapshot.

        Enforces freshness via cache_ttl to ensure stale quotes are never served.
        """
        normalized, asset_type = classify_and_normalize(raw_symbol)
        now = time.time()

        if normalized in self.price_cache:
            cached_price, cached_at = self.price_cache[normalized]
            if (now - cached_at) <= self.cache_ttl:
                return cached_price

        if asset_type == "CRYPTO":
            price = await self.binance.fetch_price(normalized)
        else:
            price = await self.yahoo.fetch_price(normalized)

        if price is not None:
            self.price_cache[normalized] = (price, now)
        return price

    async def _handle_price_tick(self, symbol: str, price: float) -> None:
        """Internal dispatch called whenever Binance or Yahoo reports a price."""
        symbol_upper = symbol.upper()
        self.price_cache[symbol_upper] = (price, time.time())

        # Notify listeners concurrently
        if self._listeners:
            tasks = [listener(symbol_upper, price) for listener in self._listeners]
            await asyncio.gather(*tasks, return_exceptions=True)

    def start(self) -> None:
        """Start both Binance WebSocket stream and Yahoo Finance polling worker."""
        self.binance.start_stream(self._handle_price_tick)
        if self._active_non_crypto_supplier:
            self.yahoo.start_polling(self._active_non_crypto_supplier, self._handle_price_tick)
        logger.info("UnifiedPriceFeed started with hybrid market engines.")

    async def stop(self) -> None:
        """Gracefully shutdown market data feeds."""
        await asyncio.gather(
            self.binance.stop(),
            self.yahoo.stop(),
            return_exceptions=True,
        )
        logger.info("UnifiedPriceFeed stopped.")
