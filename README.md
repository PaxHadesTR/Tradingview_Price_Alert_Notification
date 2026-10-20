# Autonomous Market Price Alert & Discord Bot Engine

A high-performance, self-hosted, autonomous price monitoring and notification service designed to bypass TradingView free-tier alert limits.

Run your own alert service 24/7 on **Coolify** or Docker. Set alerts for **Crypto (Binance)**, **Borsa Istanbul (BIST)**, **US Equities**, **Forex**, and **Commodities (Gold/Silver/Oil)** directly from **Discord** via modern Slash Commands.

---

## Key Features

1. **Independent of TradingView Plan Limits**:
   - Free TradingView accounts limit you to 1 or very few alerts. This service tracks unlimited alerts on your own infrastructure for $0.
2. **Hybrid Real-Time Market Feeds**:
   - **Binance WebSocket Stream (`!miniTicker@arr`)**: Sub-second ticker stream for all Binance crypto pairs with zero API key required.
   - **Yahoo Finance Async REST Feed**: Periodic polling for non-crypto assets (BIST `.IS`, US Stocks, Forex `=X`, Gold `GC=F`).
3. **Interactive Discord Bot with Slash Commands**:
   - `/alert set <symbol> <target_price> [note]`: Auto-detects whether it is an `ABOVE` breakout or `BELOW` breakdown based on current price.
   - `/alert list [status]`: Neatly formatted embed showing your active or triggered alerts.
   - `/alert delete <alert_id>`: Cancel any alert by ID.
   - `/price <symbol>`: Check live price for any asset.
   - **Interactive Buttons**: Dispatched notifications feature "🔄 Yeniden Kur" and "🗑 Temizle" buttons right on the embed!
4. **Quota & Stale Alert Protections**:
   - Configurable `MAX_ACTIVE_ALERTS` (e.g. 100) to protect server resources.
   - Automatic expiration cleaner for forgotten alerts older than `ALERT_EXPIRY_DAYS` (e.g. 180 days / 6 months).
5. **Persistent SQLite Database**:
   - Uses `aiosqlite` with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) in `./data/alerts.db`, ensuring alerts survive container redeployments.
6. **Coolify-Ready**:
   - Multi-stage non-root `Dockerfile`, `/healthz` and `/live` probes, and `docker-compose.yml` with persistent volume mapping.
7. **Backwards Compatible Webhook Ingestion**:
   - Still supports receiving standard TradingView webhooks (`/webhook/{secret_token}`).

---

## Discord Bot Commands

| Command | Description | Example |
| :--- | :--- | :--- |
| `/alert set <symbol> <price> [note]` | Creates a new price threshold alert | `/alert set symbol:BTCUSDT target_price:72000 note:Direnç kırılımı` |
| `/alert set symbol:THYAO target_price:360` | Auto-normalizes to `THYAO.IS` | `/alert set symbol:THYAO target_price:360` |
| `/alert set symbol:GOLD target_price:2750` | Auto-routes to Gold futures (`GC=F`) | `/alert set symbol:GOLD target_price:2750` |
| `/alert list [status]` | Lists your alerts (Active, Triggered, All) | `/alert list status:Aktif Alarmlar` |
| `/alert delete <id>` | Cancels an active alert by ID | `/alert delete alert_id:4` |
| `/price <symbol>` | Instant price query | `/price symbol:SOLUSDT` |

---

## Supported Symbol Formats

- **Crypto**: `BTCUSDT`, `ETHUSDT`, `SOLUSDC`, `PEPEUSDT` (Binance pairs)
- **Borsa Istanbul**: `THYAO`, `ASELS`, `GARAN`, `EREGL` (auto-appends `.IS` if omitted) or `THYAO.IS`
- **Forex**: `USDTRY`, `EURTRY`, `EURUSD` (auto-appends `=X`) or `USDTRY=X`
- **Commodities**: `GOLD` / `ALTIN` (`GC=F`), `SILVER` / `GUMUS` (`SI=F`), `BRENT` (`BZ=F`)
- **US Stocks**: `AAPL`, `TSLA`, `NVDA`, `MSFT`

---

## Coolify & Docker Deployment

### 1. Discord Bot Token Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a **New Application** -> **Bot**.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent** (and Server Members if needed).
4. Copy the **Token** into `DISCORD_BOT_TOKEN`.
5. Under **OAuth2 -> URL Generator**, check `bot` and `applications.commands`.
   Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`.
6. Invite the bot to your Discord server using the generated URL.

### 2. Coolify Configuration
In your Coolify service, configure Environment Variables:

```env
# Bot & Channel Configuration
DISCORD_BOT_TOKEN=your_bot_token_from_developer_portal
DISCORD_ALERT_CHANNEL_ID=your_discord_channel_id_here

# Engine Quotas
MAX_ACTIVE_ALERTS=100
ALERT_EXPIRY_DAYS=180
SQLITE_DB_PATH=/app/data/alerts.db

# Optional Webhook Forwarding
WEBHOOK_SECRET=your_secret_passphrase
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Coolify mounts `./data:/app/data` to ensure the SQLite database (`alerts.db`) persists across deployments.

---

## Running Automated Tests

```bash
python -m pytest tests -v
```
All 36 tests pass with 100% test coverage for authentication, dual parsers, token bucket rate limiter, SQLite transactions, symbol classification, and alert triggers.
