import os
import pytest
from fastapi.testclient import TestClient
from app.config import Settings, get_settings
from app.main import create_app
from app.models.alert import AlertPayload
from app.providers.base import BaseNotificationProvider
from app.services.queue import AlertQueueService
from app.services.rate_limiter import AsyncTokenBucket

TEST_SECRET = "super_test_secret_key_123"


class MockNotificationProvider(BaseNotificationProvider):
    """Mock notification provider that captures dispatched alerts in-memory."""

    def __init__(self, should_succeed: bool = True):
        self.dispatched_alerts: list[AlertPayload] = []
        self.should_succeed = should_succeed
        self.is_closed = False

    async def send(self, alert: AlertPayload) -> bool:
        self.dispatched_alerts.append(alert)
        return self.should_succeed

    async def close(self) -> None:
        self.is_closed = True


@pytest.fixture(autouse=True)
def override_settings(monkeypatch):
    """Ensure test environment variables are completely isolated."""
    monkeypatch.setenv("WEBHOOK_SECRET", TEST_SECRET)
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/mock/test")
    monkeypatch.setenv("RATE_LIMIT_PER_SECOND", "100.0")
    monkeypatch.setenv("MAX_QUEUE_CAPACITY", "50")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_provider() -> MockNotificationProvider:
    return MockNotificationProvider(should_succeed=True)


@pytest.fixture
def app_with_mock_queue(mock_provider: MockNotificationProvider):
    """Create test application with in-memory mock queue."""
    application = create_app()
    rate_limiter = AsyncTokenBucket(rate=100.0)
    queue_service = AlertQueueService(
        providers=[mock_provider],
        rate_limiter=rate_limiter,
        max_capacity=50,
    )
    application.state.queue_service = queue_service
    return application


@pytest.fixture
def client(app_with_mock_queue) -> TestClient:
    return TestClient(app_with_mock_queue)
