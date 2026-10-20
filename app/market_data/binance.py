import asyncio
import json
import logging
from typing import Callable, Coroutine, Dict, Optional
import httpx
import websockets

logger = logging.getLogger(__name__)


class BinanceMarketFeed:
    """Asynchronous Binance market data feed combining REST snapshot and real-time WebSocket stream."""

    def __init__(
        self,
        ws_url: str = "wss://stream.binance.com:9443/ws/!miniTicker@arr",
        rest_api_url: str = "https://api.binance.com/api/v3/ticker/price",
        timeout_seconds: float = 8.0,
    ) -> None:
        self.ws_url = ws_url
        self.rest_api_url = rest_api_url
        self.timeout = timeout_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def fetch_price(self, symbol: str) -> Optional[float]:
        """Fetch immediate spot price snapshot from Binance REST API."""
        symbol_clean = symbol.upper().strip()
        client = self._client or httpx.AsyncClient(timeout=self.timeout)
        try:
            response = await client.get(self.rest_api_url, params={"symbol": symbol_clean})
            if response.status_code == 200:
                data = response.json()
                return float(data["price"])
            logger.warning("Binance REST API returned status %d for symbol %s", response.status_code, symbol_clean)
            return None
        except Exception as e:
            logger.error("Failed fetching Binance price for %s: %s", symbol_clean, e)
            return None
        finally:
            if not self._client:
                await client.aclose()

    def start_stream(self, on_price_update: Callable[[str, float], Coroutine[None, None, None]]) -> None:
        """Start background WebSocket consumer to stream real-time price updates for all crypto symbols."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._ws_loop(on_price_update), name="binance_ws_stream")
        logger.info("Started Binance WebSocket background stream on %s", self.ws_url)

    async def stop(self) -> None:
        """Stop WebSocket background stream and close HTTP client."""
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
        logger.info("Binance market feed stopped.")

    async def _ws_loop(self, on_price_update: Callable[[str, float], Coroutine[None, None, None]]) -> None:
        """Resilient WebSocket loop with automatic reconnect and exponential backoff."""
        backoff = 2.0
        while self._running:
            try:
                logger.debug("Connecting to Binance WebSocket %s...", self.ws_url)
                async with websockets.connect(self.ws_url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info("Connected to Binance WebSocket market stream.")
                    backoff = 2.0  # Reset backoff on successful connection

                    while self._running:
                        msg = await ws.recv()
                        try:
                            data = json.loads(msg)
                            # !miniTicker@arr emits a list of ticker objects
                            if isinstance(data, list):
                                for item in data:
                                    s = item.get("s")
                                    c = item.get("c")
                                    if s and c:
                                        await on_price_update(s.upper(), float(c))
                            elif isinstance(data, dict):
                                s = data.get("s")
                                c = data.get("c")
                                if s and c:
                                    await on_price_update(s.upper(), float(c))
                        except Exception as parse_err:
                            logger.debug("Error processing miniTicker tick: %s", parse_err)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                logger.warning("Binance WebSocket disconnected (%s). Reconnecting in %.1fs...", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)
