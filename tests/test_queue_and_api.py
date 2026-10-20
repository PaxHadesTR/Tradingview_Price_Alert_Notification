import asyncio
import pytest
from fastapi.testclient import TestClient
from tests.conftest import TEST_SECRET, MockNotificationProvider
from app.models.alert import AlertPayload
from app.services.queue import AlertQueueService
from app.services.rate_limiter import AsyncTokenBucket


@pytest.mark.asyncio
async def test_full_pipeline_ingest_and_dispatch(
    mock_provider: MockNotificationProvider,
):
    rate_limiter = AsyncTokenBucket(rate=1000.0)
    queue = AlertQueueService(
        providers=[mock_provider],
        rate_limiter=rate_limiter,
        max_capacity=50,
    )
    queue.start()
    alert = AlertPayload(
        ticker="SOLUSDT",
        action="BUY",
        price=195.50,
        strategy="MACD Golden Cross",
    )
    enqueued = queue.enqueue(alert)
    assert enqueued is True

    # Give async queue worker time to process item
    await asyncio.sleep(0.05)

    assert len(mock_provider.dispatched_alerts) == 1
    dispatched = mock_provider.dispatched_alerts[0]
    assert dispatched.ticker == "SOLUSDT"
    assert dispatched.action == "BUY"
    assert dispatched.price == 195.50

    await queue.stop()


def test_queue_overflow_rejection():
    # Capacity of 2 items
    rate_limiter = AsyncTokenBucket(rate=0.01)  # slow so items stay in queue
    mock = MockNotificationProvider()
    queue = AlertQueueService(
        providers=[mock],
        rate_limiter=rate_limiter,
        max_capacity=2,
    )
    alert = AlertPayload(ticker="BTCUSDT", action="BUY")
    assert queue.enqueue(alert) is True
    assert queue.enqueue(alert) is True
    # 3rd item should be rejected (buffer full)
    assert queue.enqueue(alert) is False
    assert queue.stats["total_failed"] == 1


def test_healthz_endpoint(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "queue" in data


def test_live_endpoint(client: TestClient):
    response = client.get("/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
