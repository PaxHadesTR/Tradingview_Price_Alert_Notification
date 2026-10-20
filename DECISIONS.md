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
