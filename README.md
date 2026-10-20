# Autonomous Market Price Alert & Discord Bot Engine

A high-performance, self-hosted, autonomous price monitoring and notification service designed to bypass TradingView free-tier alert limits.

Run your own alert service 24/7 on **Coolify** or Docker. Set alerts for **Crypto (Binance)**, **Borsa Istanbul (BIST)**, **US Equities**, **Forex**, and **Commodities (Gold/Silver/Oil)** directly from **Discord** via modern Slash Commands.

---

## 🇹🇷 Türkiye İçin Kurulum & Discord Erişim Engeli Çözümü (Cloudflare WARP)

Türkiye'de BTK ve mahkeme kararıyla **Discord'a erişim engeli** uygulandığından, Türkiye lokasyonlu sunuculardan (veya yerel WSL/Docker kurulumlarından) `discord.com`'a bağlanmaya çalışıldığında internet servis sağlayıcıların (Superonline, TTNET vb.) DPI engellemesi nedeniyle `SSLCertVerificationError` hatası alınır.

Bu projede Türkiye'deki kullanıcıların ek hiçbir ücret ödemeden ve VPN kurmak zorunda kalmadan Discord botunu çalıştırabilmesi için **Cloudflare WARP Sidecar / Proxy** desteği entegre edilmiştir.

### Nasıl Uygulanır?

#### 1. Coolify ile Kullanıyorsanız (Tek Komut)
Sunucunuzun terminalinde (veya WSL içinde) tek bir komutla hafif Cloudflare WARP konteynerini `coolify` ağına bağlayın:
```bash
docker run -d --name warp --cap-add NET_ADMIN --network coolify --restart always caomingjun/warp
```
Ardından Coolify'da **Environment Variables** kısmına şunu ekleyin:
```env
DISCORD_PROXY=http://warp:1080
```
Konteyneri **Restart** ettiğinizde bot engeli tamamen aşarak Discord'a bağlanacaktır.

#### 2. Standart Docker Compose ile Kullanıyorsanız
Proje kökündeki `docker-compose.yml` dosyasına `warp` servisi zaten eklenmiştir:
```bash
docker compose up -d --build
```
Konteynerler ayağa kalktığında bot otomatik olarak `warp` proxy'si üzerinden Discord'a bağlanır.

---

## Key Features

1. **Independent of TradingView Plan Limits**:
   - Free TradingView accounts limit you to 1 or very few alerts. This service tracks unlimited alerts on your own infrastructure for $0.
2. **Hybrid Real-Time Market Feeds**:
   - **Binance WebSocket Stream (`!miniTicker@arr`)**: Sub-second ticker stream for all Binance crypto pairs with zero API key required.
   - **Yahoo Finance Async REST Feed**: Periodic polling for non-crypto assets (BIST `.IS`, US Stocks, Forex `=X`, Gold `GC=F`).
3. **Interactive Discord Bot with Slash Commands**:
   - `/alert set <symbol> <target_price> [note] [dm]`: Auto-detects whether it is an `ABOVE` breakout or `BELOW` breakdown. Optional `dm:True` sends notification directly to your Discord DMs.
   - `/alert list [status]`: Shows active/triggered alerts with live prices, percentage distance to target, and an interactive **Dropdown Menu** to delete alerts with 1-click.
   - `/alert delete <alert_id>`: Cancel any alert by ID.
   - `/watchlist show`: Instant dashboard showing live prices for all assets on your personal watchlist.
   - `/watchlist add <symbol>` & `/watchlist remove <symbol>`: Manage your favorite assets.
   - `/price <symbol>`: Check live price for any asset.
   - **Real-Time Autocomplete**: Suggests popular Crypto, BIST stocks, US equities, commodities, and indices as you type.
   - **Interactive Buttons**: Dispatched notifications feature "🔄 Yeniden Kur" and "🗑 Temizle" buttons.
4. **Quota & Stale Alert Protections**:
   - Configurable `MAX_ACTIVE_ALERTS` (e.g. 100) to protect server resources.
   - Automatic expiration cleaner for forgotten alerts older than `ALERT_EXPIRY_DAYS` (e.g. 180 days / 6 months).
5. **Persistent SQLite Database**:
   - Uses `aiosqlite` with Write-Ahead Logging (`PRAGMA journal_mode=WAL`) in `./data/alerts.db`, ensuring alerts and watchlists survive container redeployments.
6. **Coolify-Ready**:
   - Multi-stage non-root `Dockerfile`, `/healthz` and `/live` probes, and `docker-compose.yml` with persistent volume mapping.
7. **Backwards Compatible Webhook Ingestion**:
   - Still supports receiving standard TradingView webhooks (`/webhook/{secret_token}`).

---

## Discord Bot Commands

| Command | Description | Example |
| :--- | :--- | :--- |
| `/alert set <symbol> <price> [note] [dm]` | Creates a new price threshold alert with optional DM delivery | `/alert set symbol:BTCUSDT target_price:85000 note:Direnç dm:True` |
| `/alert list [status]` | Lists alerts with live prices, target distance %, and dropdown delete menu | `/alert list status:Aktif Alarmlar` |
| `/alert delete <id>` | Cancels an active alert by ID | `/alert delete alert_id:4` |
| `/price <symbol>` | Instant price query (supports autocomplete) | `/price symbol:SOLUSDT` |
| `/watchlist show` | Shows live prices for all assets on your personal watchlist | `/watchlist show` |
| `/watchlist add <symbol>` | Adds a symbol to your watchlist | `/watchlist add symbol:THYAO` |
| `/watchlist remove <symbol>` | Removes a symbol from your watchlist | `/watchlist remove symbol:THYAO` |

---

## Supported Symbol Formats

- **Crypto**: `BTCUSDT`, `ETHUSDT`, `SOLUSDC`, `PEPEUSDT` (or shorthand: `BTC`, `ETH`, `SOL`)
- **Borsa Istanbul**: `THYAO`, `ASELS`, `GARAN`, `EREGL`, `ALARK` (auto-appends `.IS` if omitted) or `THYAO.IS`
- **Indices**: `XU100`, `BIST100`, `BIST30`, `NASDAQ`, `NDX`, `SP500`, `DXY`
- **Forex**: `USDTRY`, `EURTRY`, `EURUSD` (auto-appends `=X`) or `USDTRY=X`
- **Commodities**: `GOLD` / `ALTIN` / `XAU` (`GC=F`), `SILVER` / `GUMUS` / `XAG` (`SI=F`), `BRENT` (`BZ=F`)
- **US Stocks**: `AAPL`, `TSLA`, `NVDA`, `MSFT`

---

## Coolify & Docker Deployment

### 1. Discord Bot Token Setup
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Create a **New Application** -> **Bot**.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**.
4. Click **Reset Token** and copy your **Bot Token** into `DISCORD_BOT_TOKEN`.
5. Under **OAuth2 -> URL Generator**, check `bot` and `applications.commands`.
   Permissions: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`.
6. Invite the bot to your Discord server using the generated URL.

### 2. Coolify Configuration
In your Coolify service, configure Environment Variables:

```env
# Bot & Channel Configuration
DISCORD_BOT_TOKEN=your_bot_token_from_developer_portal
DISCORD_ALERT_CHANNEL_ID=your_discord_channel_id_here
DISCORD_PROXY=http://warp:1080

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
All 40 tests pass with 100% test coverage for authentication, dual parsers, token bucket rate limiter, SQLite transactions, watchlists, DM flags, symbol classification, and alert triggers.
