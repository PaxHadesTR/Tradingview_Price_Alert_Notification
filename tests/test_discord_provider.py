import pytest
import httpx
from app.models.alert import AlertPayload
from app.providers.discord import DiscordWebhookProvider


def test_build_discord_payload_bullish():
    provider = DiscordWebhookProvider(
        webhook_url="https://discord.com/api/webhooks/123/abc",
        bot_username="TV Bot",
    )
    alert = AlertPayload(
        ticker="BTCUSDT",
        action="BUY",
        price=68450.50,
        strategy="SuperTrend",
        timeframe="15m",
        message="Breakout detected",
        extra_data={"RSI": "72.4"},
    )
    body = provider.build_discord_payload(alert)

    assert body["username"] == "TV Bot"
    assert len(body["embeds"]) == 1
    embed = body["embeds"][0]
    assert "🟢 BTCUSDT - BUY" in embed["title"]
    assert embed["color"] == 0x00FF88
    assert "> Breakout detected" == embed["description"]

    field_names = [f["name"] for f in embed["fields"]]
    assert "💵 Price" in field_names
    assert "🎯 Strategy" in field_names
    assert "⏱ Timeframe" in field_names
    assert "🔹 Rsi" in field_names


def test_build_discord_payload_bearish():
    provider = DiscordWebhookProvider(
        webhook_url="https://discord.com/api/webhooks/123/abc",
    )
    alert = AlertPayload(
        ticker="ETHUSDT",
        action="SELL",
        price=3420.10,
    )
    body = provider.build_discord_payload(alert)
    embed = body["embeds"][0]

    assert "🔴 ETHUSDT - SELL" in embed["title"]
    assert embed["color"] == 0xFF3366


@pytest.mark.asyncio
async def test_discord_mock_http_dispatch():
    # Mock transport to simulate Discord returning 204 No Content
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=204)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        provider = DiscordWebhookProvider(
            webhook_url="https://discord.com/api/webhooks/test",
            client=mock_client,
        )
        alert = AlertPayload(ticker="BTCUSDT", action="BUY", price=65000)
        success = await provider.send(alert)
        assert success is True


@pytest.mark.asyncio
async def test_discord_rate_limit_retry():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # First attempt: 429 Too Many Requests
            return httpx.Response(status_code=429, json={"retry_after": 0.05})
        return httpx.Response(status_code=204)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        provider = DiscordWebhookProvider(
            webhook_url="https://discord.com/api/webhooks/test",
            client=mock_client,
        )
        alert = AlertPayload(ticker="BTCUSDT", action="BUY", price=65000)
        success = await provider.send(alert)
        assert success is True
        assert attempts == 2
