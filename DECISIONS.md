# Architecture Decision Records (ADR)

## ADR-001: Choice of Core Runtime & Web Framework (Python 3.15 + FastAPI)
* **Date**: 2026-10-20
* **Status**: ACCEPTED
* **Context**: The system must ingest real-time HTTP webhooks from TradingView, validate authentication/payloads, and reliably dispatch alerts under burst conditions without blocking I/O. Target deployment is Coolify.
* **Decision**: Adopt Python 3.15 with FastAPI and `uvicorn`. Leverage `pydantic` v2 for strict runtime schema validation and `httpx` for non-blocking asynchronous HTTP outbound requests.
* **Outcome**: Modern asynchronous event handling, automatic OpenAPI/Swagger docs, native typed data structures.

---

## ADR-002: Notification Dispatch Architecture (Discord Webhook with Provider Abstraction)
* **Date**: 2026-10-20
* **Status**: ACCEPTED
* **Context**: Alerts need to be delivered to Discord immediately upon trigger. The system must support high reliability without keeping a fragile stateful websocket connection alive unnecessarily.
* **Decision**: Use Discord Webhook via asynchronous HTTP POST as the primary dispatcher, wrapping it behind an abstract `BaseNotificationProvider` interface.
* **Outcome**: Minimal resource footprint, instant delivery, zero socket connection management.

---

## ADR-003: Rate Limiting & Burst Protection via In-Memory Async Queue
* **Date**: 2026-10-20
* **Status**: ACCEPTED
* **Decision**: Implement an in-memory `asyncio.Queue` consumer worker with a Leaky Bucket / Token Bucket rate limiter.
* **Outcome**: Zero external infrastructure dependency, 100% protection against Discord rate limits.

---

## ADR-004: Dual Payload Ingestion and Passphrase Verification
* **Date**: 2026-10-20
* **Status**: ACCEPTED
* **Decision**: Support both payload `passphrase` verification and URL path secret verification (`/webhook/{secret_token}`).
* **Outcome**: Resilient ingestion that never fails due to TradingView formatting quirks while ensuring zero unauthorized alert injection.

---

## ADR-005: Autonomous Hybrid Price Feed Engine (Binance WS + Yahoo REST)
* **Date**: 2026-10-20
* **Status**: ACCEPTED
* **Context**: Free TradingView accounts limit alert quotas severely. The engine must track prices independently without depending on a paid TradingView plan, across both Crypto (Binance) and Equities/Forex/Commodities (BIST, US Stocks, Gold, Currency).
* **Decision**: Implement a dual-engine market data feed:
  1. *Binance Public WebSocket Stream* for real-time crypto ticker data (sub-second latency, zero API key, zero cost).
  2. *Yahoo Finance Async REST Client* (`query1.finance.yahoo.com`) for non-crypto symbols (BIST `.IS`, US Equities, Forex `=X`, Commodities `=F`) with a configurable async polling cycle (default 15-30s).
* **Rejected Alternatives**:
  - *Third-party paid API keys (AlphaVantage, TwelveData)*: Incurs costs and API limits.
  - *Selenium / Headless browser scraping*: Fragile, high RAM consumption on Coolify containers.
* **Trade-offs**: Non-crypto assets update with 15-30s interval instead of sub-second websockets, which is well within standard threshold price alert tolerances.
* **Outcome**: 100% free, unlimited alert capability across Crypto, BIST, US Stocks, and Forex.

---

## ADR-006: Discord Bot with Slash Commands & SQLite Persistence
* **Date**: 2026-10-20
* **Status**: ACCEPTED
* **Context**: Users must be able to add, inspect, and delete price alerts directly from Discord without writing code. Alerts must survive container restarts.
* **Decision**: Integrate `discord.py` running on the same asyncio event loop. Use `aiosqlite` with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) storing alerts in `./data/alerts.db`. Implement Slash Commands (`/alert set`, `/alert list`, `/alert delete`, `/price`) and interactive button views.
* **Outcome**: Rich native Discord interface, persistent alert state, atomic transactions, zero external database setup required.

---

## ADR-007: Outbound Proxy via Cloudflare WARP Sidecar for Turkey ISP DPI Bypass
* **Date**: 2026-10-21
* **Status**: ACCEPTED
* **Context**: In Turkey, ISP-level DPI blocks on `discord.com` cause `SSLCertVerificationError` when connecting to Discord gateways.
* **Decision**: Add `caomingjun/warp` sidecar container in `docker-compose.yml` and provide standard `DISCORD_PROXY=http://warp:1080` parameter for Discord bot connection.
* **Outcome**: Seamless Discord connectivity from Turkey servers without paying for external VPN services.

---

## ADR-008: Percentage-Based Alert Parsing and Human Input Normalization
* **Date**: 2026-10-26
* **Status**: ACCEPTED
* **Context**: Real traders often want to set alerts based on percentage moves (e.g. `+5%`, `-3%`) from current prices, or input prices with localized decimal conventions (e.g. `150,50` or `70k`).
* **Decision**: Implement `parse_target_price_input` supporting percentage offsets, localized comma decimals, human multipliers (`k`/`m`), and stripping currency symbols.
* **Outcome**: Human-centric user experience that prevents input errors and eliminates manual calculations for traders.

---

## ADR-009: In-Memory Freshness TTL Cache and Watchlist Polling Aggregation
* **Date**: 2026-10-26
* **Status**: ACCEPTED
* **Context**: Cached market quotes must not serve stale prices across hours, and assets monitored in user watchlists should be pre-warmed.
* **Decision**: Implement timestamped price cache tuples with a 20-second TTL in `UnifiedPriceFeed`, and aggregate both active alerts and user watchlists into the Yahoo Finance background polling supplier.
* **Outcome**: Instant sub-second quote lookups in `/watchlist show` and `/price` while guaranteeing quotes never become stale.

---

## ADR-010: Persistent Discord Bot Supervisor with Bot-Aware Healthcheck & Gateway Observability
* **Date**: 2026-10-29
* **Status**: ACCEPTED
* **Context**: Network proxy drops (e.g. WARP proxy restarts) or Discord gateway disconnections caused `bot.start()` to terminate permanently. Reusing the closed client threw `RuntimeError: Cannot reuse a closed Discord client`. Concurrently, `/live` and `/healthz` returned 200 OK blindly, preventing Coolify/Docker from detecting offline status and restarting the container. Disconnection events were also missing from stdout logs.
* **Decision**:
  1. *Persistent Supervisor Loop in `app/main.py`*: Implement an infinite supervisor loop with exponential backoff (`5s -> 10s -> 30s -> max 60s`). Upon any gateway termination or failure, clean up the dead client (`await bot.close()`), create a fresh `DiscordAlertBot` instance, atomically update `app.state.discord_bot` and `DiscordBotNotificationProvider.bot`, and reconnect. Immediately abort supervisor on fatal non-recoverable authentication errors (`LoginFailure`, `PrivilegedIntentsRequired`) to prevent Discord API bans.
  2. *Bot-Aware Healthcheck in `app/routes/health.py`*: Check `settings.is_discord_bot_configured`. If enabled, verify supervisor task liveness, bot instance state, and ready status. A 20s startup grace period covers all unready/reconnecting states during cold container boot to prevent premature deployment aborts in Coolify. If offline or dead after grace period, return HTTP 503 to trigger container recovery.
  3. *Gateway Lifecycle Observability*: Implement `on_connect`, `on_resumed`, `on_disconnect`, and `on_error` listeners in `DiscordAlertBot`, and enforce INFO level for `discord` logger hierarchy.
  4. *Alert Delivery Integrity & Rate Limit Protection*: Add `reset_alert_to_active` rollback in `app/database/db.py` when dispatch fails or client is reconnecting, preventing lost alerts. Implement single global command sync in `app/bot/client.py` to prevent hitting Discord's 200/day slash command rate limit during reconnect cycles.
* **Outcome**: Resilient self-healing bot connections under proxy/network instability, zero deadlocks, transparent logging, zero lost alerts, and reliable container orchestration via Docker healthchecks.
