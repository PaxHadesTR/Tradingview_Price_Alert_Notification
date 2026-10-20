import asyncio
import time
import pytest
from app.services.rate_limiter import AsyncTokenBucket


@pytest.mark.asyncio
async def test_token_bucket_initial_capacity():
    limiter = AsyncTokenBucket(rate=10.0, capacity=5.0)
    assert limiter.tokens == 5.0

    # Acquire 3 tokens immediately without delay
    start = time.monotonic()
    await limiter.acquire(3.0)
    duration = time.monotonic() - start
    assert duration < 0.1
    assert limiter.tokens < 2.5


@pytest.mark.asyncio
async def test_token_bucket_rate_throttling():
    # Rate: 5 tokens/second. Burst capacity: 1 token.
    limiter = AsyncTokenBucket(rate=5.0, capacity=1.0)

    # First token is consumed immediately
    await limiter.acquire(1.0)

    # Second token requires waiting ~0.20s
    start = time.monotonic()
    await limiter.acquire(1.0)
    duration = time.monotonic() - start

    assert duration >= 0.15


@pytest.mark.asyncio
async def test_token_bucket_invalid_rate():
    with pytest.raises(ValueError):
        AsyncTokenBucket(rate=0.0)
