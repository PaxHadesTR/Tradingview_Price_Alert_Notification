import asyncio
import logging
from typing import Callable, Coroutine, List, Optional
import httpx

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


class YahooFinanceFeed:
    """Async client for fetching stock, Forex, and commodity prices via Yahoo Finance API."""

    def __init__(
        self,
        poll_interval_seconds: float = 20.0,
        timeout_seconds: float = 8.0,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.timeout = timeout_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def fetch_price(self, symbol: str) -> Optional[float]:
        """Fetch latest price snapshot for non-crypto symbols (BIST, US Equities, Forex, Gold)."""
        symbol_clean = symbol.upper().strip()
        price = await self._fetch_direct_price(symbol_clean)
        if price is not None:
            return price

        # If not found and symbol has no extension, attempt BIST fallback (.IS)
        if "." not in symbol_clean and "=" not in symbol_clean and "^" not in symbol_clean:
            bist_symbol = f"{symbol_clean}.IS"
            logger.debug("Attempting BIST fallback lookup for %s -> %s", symbol_clean, bist_symbol)
            bist_price = await self._fetch_direct_price(bist_symbol)
            if bist_price is not None:
                return bist_price

        return None

    async def _fetch_direct_price(self, symbol_clean: str) -> Optional[float]:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol_clean}"
        params = {"interval": "1m", "range": "1d"}

        client = self._client or httpx.AsyncClient(headers=HEADERS, timeout=self.timeout)
        try:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result")
                if result and len(result) > 0:
                    meta = result[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    if price is not None:
                        return float(price)

                    # Fallback to last close indicator
                    quote = result[0].get("indicators", {}).get("quote", [{}])[0]
                    closes = quote.get("close", [])
                    valid_closes = [c for c in closes if c is not None]
                    if valid_closes:
                        return float(valid_closes[-1])

            logger.debug("Yahoo Finance returned status %d for symbol %s", response.status_code, symbol_clean)
            return None
        except Exception as e:
            logger.debug("Failed fetching Yahoo price for %s: %s", symbol_clean, e)
            return None
        finally:
            if not self._client:
                await client.aclose()

    def start_polling(
        self,
        get_active_symbols: Callable[[], Coroutine[None, None, List[str]]],
        on_price_update: Callable[[str, float], Coroutine[None, None, None]],
    ) -> None:
        """Start periodic background polling task for active non-crypto symbols."""
        if self._running:
            return
        self._running = True
        self._client = httpx.AsyncClient(headers=HEADERS, timeout=self.timeout)
        self._task = asyncio.create_task(
            self._poll_loop(get_active_symbols, on_price_update),
            name="yahoo_finance_poller",
        )
        logger.info("Started Yahoo Finance polling background worker (interval: %.1fs).", self.poll_interval)

    async def stop(self) -> None:
        """Stop polling background worker."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        logger.info("Yahoo Finance feed stopped.")

    async def _poll_loop(
        self,
        get_active_symbols: Callable[[], Coroutine[None, None, List[str]]],
        on_price_update: Callable[[str, float], Coroutine[None, None, None]],
    ) -> None:
        while self._running:
            try:
                symbols = await get_active_symbols()
                if symbols:
                    logger.debug("Polling Yahoo Finance for %d active symbols: %s", len(symbols), symbols)
                    tasks = [self._poll_symbol(s, on_price_update) for s in set(symbols)]
                    await asyncio.gather(*tasks, return_exceptions=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Unexpected error in Yahoo polling loop: %s", e, exc_info=True)

            await asyncio.sleep(self.poll_interval)

    async def _poll_symbol(
        self,
        symbol: str,
        on_price_update: Callable[[str, float], Coroutine[None, None, None]],
    ) -> None:
        price = await self.fetch_price(symbol)
        if price is not None:
            await on_price_update(symbol, price)
