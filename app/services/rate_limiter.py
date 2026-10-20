import asyncio
import time
from typing import Optional


class AsyncTokenBucket:
    """Asynchronous token bucket rate limiter to prevent downstream API 429 throttling."""

    def __init__(self, rate: float = 2.0, capacity: Optional[float] = None) -> None:
        """
        :param rate: Tokens added per second.
        :param capacity: Maximum bucket capacity for bursts (defaults to 2 * rate).
        """
        if rate <= 0:
            raise ValueError("Rate must be greater than zero.")
        self.rate = rate
        self.capacity = capacity if capacity is not None else max(rate * 2.0, 1.0)
        self.tokens = self.capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until the requested number of tokens are available."""
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self.last_update
                self.last_update = now

                # Replenish tokens based on elapsed time
                self.tokens = min(self.capacity, self.tokens + (elapsed * self.rate))

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Calculate wait duration for needed tokens
                needed = tokens - self.tokens
                wait_time = needed / self.rate

            # Sleep outside the lock so other tasks aren't blocked from checking
            await asyncio.sleep(wait_time)
