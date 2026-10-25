import asyncio
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.models.alert import AlertPayload
from app.providers.base import BaseNotificationProvider

logger = logging.getLogger(__name__)


class DiscordWebhookProvider(BaseNotificationProvider):
    """Dispatches TradingView alerts to Discord channels using Discord Webhook API."""

    def __init__(
        self,
        webhook_url: str,
        bot_username: str = "TradingView Alert",
        avatar_url: Optional[str] = None,
        timeout_seconds: float = 10.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.bot_username = bot_username
        self.avatar_url = avatar_url
        self.timeout = timeout_seconds
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=self.timeout)

    async def send(self, alert: AlertPayload) -> bool:
        """Construct Discord Embed and POST to the configured Webhook URL."""
        if not self.webhook_url:
            logger.warning("Discord webhook URL is not configured. Alert skipped.")
            return False

        payload = self.build_discord_payload(alert)

        max_retries = 3
        backoff = 1.0

        for attempt in range(1, max_retries + 1):
            try:
                response = await self._client.post(self.webhook_url, json=payload)

                if response.status_code in (200, 204):
                    logger.info("Successfully dispatched alert to Discord: %s %s", alert.ticker, alert.action)
                    return True

                elif response.status_code == 429:
                    retry_after = 2.0
                    try:
                        rate_data = response.json()
                        retry_after = float(rate_data.get("retry_after", 2.0))
                    except Exception:
                        pass
                    logger.warning("Discord 429 Rate Limit hit. Backing off for %.2fs (Attempt %d/%d)", retry_after, attempt, max_retries)
                    await asyncio.sleep(retry_after)

                elif response.status_code >= 500:
                    logger.warning("Discord server error (HTTP %d). Retrying in %.2fs...", response.status_code, backoff)
                    await asyncio.sleep(backoff)
                    backoff *= 2

                else:
                    logger.error("Failed to send alert to Discord (HTTP %d): %s", response.status_code, response.text)
                    return False

            except (httpx.RequestError, httpx.TimeoutException) as exc:
                logger.warning("Network error while dispatching to Discord: %s. Retrying in %.2fs...", exc, backoff)
                await asyncio.sleep(backoff)
                backoff *= 2
            except Exception as e:
                logger.error("Unexpected error in Discord dispatch: %s", e, exc_info=True)
                return False

        logger.error("Exceeded maximum retries (%d) dispatching alert %s to Discord.", max_retries, alert.ticker)
        return False

    def build_discord_payload(self, alert: AlertPayload) -> Dict[str, Any]:
        """Generate structured Discord webhook JSON body containing rich Embeds."""
        # Emoji and Title formatting
        if alert.is_bullish:
            icon = "🟢"
            direction = f"BUY / {alert.normalized_action}"
        elif alert.is_bearish:
            icon = "🔴"
            direction = f"SELL / {alert.normalized_action}"
        else:
            icon = "🔔"
            direction = alert.normalized_action

        title = f"{icon} {alert.ticker} - {direction}"

        fields: List[Dict[str, Any]] = []

        if alert.price is not None:
            # Format price nicely
            if alert.price >= 1.0:
                price_str = f"${alert.price:,.2f}" if alert.price > 10 else f"${alert.price:.4f}"
            else:
                price_str = f"${alert.price:.8f}".rstrip("0")
            fields.append({"name": "💵 Price", "value": f"`{price_str}`", "inline": True})

        if alert.strategy:
            fields.append({"name": "🎯 Strategy", "value": f"`{alert.strategy}`", "inline": True})

        if alert.timeframe:
            fields.append({"name": "⏱ Timeframe", "value": f"`{alert.timeframe}`", "inline": True})

        # Add custom extra data fields (up to 5)
        if alert.extra_data:
            for k, v in list(alert.extra_data.items())[:5]:
                fields.append({"name": f"🔹 {k.capitalize()}", "value": f"`{v}`", "inline": True})

        description = None
        if alert.message:
            description = f"> {alert.message}"

        embed = {
            "title": title,
            "description": description,
            "color": alert.embed_color,
            "fields": fields,
            "timestamp": alert.timestamp,
            "footer": {
                "text": "TradingView Alert Dispatcher • Coolify",
            },
        }

        body: Dict[str, Any] = {
            "username": self.bot_username,
            "embeds": [embed],
        }

        if self.avatar_url:
            body["avatar_url"] = self.avatar_url

        return body

    async def close(self) -> None:
        """Close the underlying HTTP client session if owned."""
        if not self._external_client and not self._client.is_closed:
            await self._client.aclose()


class DiscordBotNotificationProvider(BaseNotificationProvider):
    """Dispatches TradingView alerts directly to a Discord channel using the active Discord Bot client."""

    def __init__(self, bot: Any, channel_id: int):
        self.bot = bot
        self.channel_id = channel_id

    async def send(self, alert: AlertPayload) -> bool:
        if not self.bot or not self.channel_id:
            return False

        try:
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                channel = await self.bot.fetch_channel(self.channel_id)
            if not channel:
                logger.error("DiscordBotNotificationProvider: Channel %s not found.", self.channel_id)
                return False

            import discord
            is_bullish = alert.is_bullish
            is_bearish = alert.is_bearish
            icon = "🟢" if is_bullish else ("🔴" if is_bearish else "🔔")
            direction = f"BUY / {alert.normalized_action}" if is_bullish else (
                f"SELL / {alert.normalized_action}" if is_bearish else alert.normalized_action
            )

            embed = discord.Embed(
                title=f"{icon} {alert.ticker} - {direction}",
                description=f"> {alert.message}" if alert.message else None,
                color=alert.embed_color,
            )

            if alert.price is not None:
                if alert.price >= 1.0:
                    price_str = f"${alert.price:,.2f}" if alert.price > 10 else f"${alert.price:.4f}"
                else:
                    price_str = f"${alert.price:.8f}".rstrip("0")
                embed.add_field(name="💵 Fiyat", value=f"`{price_str}`", inline=True)
            if alert.strategy:
                embed.add_field(name="🎯 Strateji", value=f"`{alert.strategy}`", inline=True)
            if alert.timeframe:
                embed.add_field(name="⏱ Zaman Dilimi", value=f"`{alert.timeframe}`", inline=True)

            if alert.extra_data:
                for k, v in list(alert.extra_data.items())[:5]:
                    embed.add_field(name=f"🔹 {k.capitalize()}", value=f"`{v}`", inline=True)

            embed.set_footer(text="TradingView Alert Dispatcher • Discord Bot")
            await channel.send(embed=embed)
            logger.info("Successfully dispatched TradingView alert via Bot to channel %s", self.channel_id)
            return True
        except Exception as e:
            logger.error("Failed dispatching alert via Discord Bot: %s", e)
            return False

    async def close(self) -> None:
        pass
