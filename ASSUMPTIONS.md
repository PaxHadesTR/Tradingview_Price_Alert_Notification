# System Invariants and Technical Assumptions

## Non-Negotiable System Invariants
1. **Autonomous Price Monitoring**: The service must monitor market prices independently of TradingView's alert infrastructure, using free public market feeds (Binance WebSocket for crypto, Yahoo Finance for non-crypto).
2. **Quota and Expiration Protection**: Active alert counts are capped globally at `MAX_ACTIVE_ALERTS` (default 100) and individually at `MAX_USER_ACTIVE_ALERTS` (default 25) to prevent resource monopolization in shared servers. Un-triggered alerts older than `ALERT_EXPIRY_DAYS` (default 180 days) are automatically marked `EXPIRED`.
3. **Atomic State & Single-Fire Guarantees**: A price threshold alert must fire exactly once upon crossing (atomic transition from `ACTIVE` to `TRIGGERED`), preventing alert spam during price volatility at the threshold border.
4. **Resilient Restart Persistence**: All user alerts must persist across Coolify container redeployments using an SQLite database with Write-Ahead Logging (`PRAGMA journal_mode=WAL`).
5. **Zero-Block Dual Process Loop**: Both FastAPI (healthcheck / webhooks) and Discord Bot Gateway run concurrently on the same non-blocking `asyncio` event loop.
6. **Price Cache Freshness (TTL)**: In-memory price cache enforces a 20-second TTL to ensure quotes queried by users or watchlists are continually refreshed and never served stale.
7. **Dual TradingView Routing**: TradingView webhook ingestion automatically falls back to the running Discord Bot client if `DISCORD_WEBHOOK_URL` is omitted, eliminating setup confusion for end-users.

## Technical Assumptions
- **Crypto Symbol Format**: Binance pairs format (e.g. `BTCUSDT`, `ETHUSDT`, `SOLUSDT`). Auto-normalized to uppercase.
- **Equity / Forex Symbol Format**: Yahoo Finance format (e.g. `THYAO.IS`, `ASELS.IS`, `AAPL`, `EURUSD=X`, `USDTRY=X`, `GC=F`). Helper normalizers automatically append `.IS` or `=X` for common Turkish symbols and currencies if omitted.
- **Discord Bot Token**: Configured via `DISCORD_BOT_TOKEN`. If absent, the Discord bot client gracefully idles without crashing FastAPI health endpoints.
