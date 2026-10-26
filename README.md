# Autonomous Market Price Alert & Discord Bot Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)](tests/)

A high-performance, self-hosted, autonomous price monitoring and notification service designed to bypass TradingView free-tier alert limits and provide institutional-grade alerts on your own infrastructure.

Run your own alert service 24/7 on **Coolify** or Docker. Set alerts for **Crypto (Binance)**, **Borsa Istanbul (BIST)**, **US Equities**, **Forex**, and **Commodities (Gold/Silver/Oil)** directly from **Discord** via modern Slash Commands, or route your **TradingView Webhooks** directly into Discord.

---

## 🇹🇷 Türkiye İçin Kurulum & Discord Erişim Engeli Çözümü (Cloudflare WARP)

Türkiye'de BTK ve mahkeme kararıyla **Discord'a erişim engeli** uygulandığından, Türkiye lokasyonlu sunuculardan (veya yerel WSL/Docker kurulumlarından) `discord.com`'a bağlanmaya çalışıldığında internet servis sağlayıcıların (Superonline, TTNET vb.) DPI engellemesi nedeniyle `SSLCertVerificationError` hatası alınır.

Bu projede Türkiye'deki kullanıcıların ek hiçbir ücret ödemeden ve VPN kurmak zorunda kalmadan Discord botunu çalıştırabilmesi için **Cloudflare WARP Sidecar / Proxy** desteği entegre edilmiştir.

### Nasıl Uygulanır?

#### 1. Coolify ile Kullanıyorsanız (Önerilen Sağlam Kurulum)
Sunucunuzun terminalinde (veya WSL içinde) Cloudflare WARP konteynerini gerekli çekirdek ağ yetkileri ve kalıcı oturum hacmiyle başlatın:
```bash
docker rm -f warp
docker run -d \
  --name warp \
  --restart always \
  --network coolify \
  --cap-add NET_ADMIN \
  --cap-add MKNOD \
  --cap-add AUDIT_WRITE \
  --sysctl net.ipv6.conf.all.disable_ipv6=0 \
  --sysctl net.ipv4.conf.all.src_valid_mark=1 \
  -e WARP_SLEEP=5 \
  -v warp_data:/var/lib/cloudflare-warp \
  caomingjun/warp:latest
```
Ardından Coolify'da **Environment Variables** kısmına şunu ekleyin:
```env
DISCORD_PROXY=http://warp:1080
```
Konteyneri **Restart** ettiğinizde bot engeli tamamen aşarak Discord'a bağlanacaktır.

> **💡 İpucu (Proxy Durum Kontrolü):**
> Bağlantı durumunu kontrol etmek için: `docker exec warp warp-cli status` (Connected yazmalıdır).
> Eğer nadiren bağlantı koparsa: `docker exec warp warp-cli connect` komutuyla hemen yeniden bağlayabilirsiniz.

#### 2. Standart Docker Compose ile Kullanıyorsanız
Proje kökündeki `docker-compose.yml` dosyasına `warp` servisi zaten eklenmiştir:
```bash
docker compose up -d --build
```
Konteynerler ayağa kalktığında bot otomatik olarak `warp` proxy'si üzerinden Discord'a bağlanır.

---

## 🌟 Öne Çıkan Özellikler (Key Features)

1. **TradingView Plan Limitlerine Son**:
   - Ücretsiz TradingView hesaplarındaki 1 alarm sınırına takılmadan, kendi sunucunuzda sınırsız sayıda alarm kurun ve takip edin.
2. **Hibrit Gerçek Zamanlı Piyasa Beslemesi (Hybrid Feeds)**:
   - **Binance WebSocket Stream (`!miniTicker@arr`)**: Tüm kripto çiftleri için milisaniyelik canlı fiyat akışı (API key gerektirmez).
   - **Yahoo Finance Async Poller**: Kripto dışı varlıklar (BIST `.IS`, ABD Hisseleri, Döviz `=X`, Altın/Petrol Vadeli `GC=F`, `BZ=F`, Endeksler) için 20 saniyelik periyodik canlı tarama.
   - **In-Memory Freshness Cache (20s TTL)**: Fiyat sorgularında eski/bayat fiyat gösterimini önleyen akıllı önbellek mekanizması.
3. **Gelişmiş Discord Slash Komutları & Kullanıcı Deneyimi**:
   - `/alert set`: Hedef fiyata veya **yüzdesel değişime** (`+5%`, `-3%`, `150,5`, `70k`) göre alarm kurma. Otomatik yön tayini (`ABOVE` / `BELOW`).
   - `/alert list`: Canlı fiyatlar, hedefe kalan yüzde mesafesi ve tek tıkla silme sağlayan açılır menü (Dropdown).
   - `/alert clear`: Tetiklenmiş veya tüm alarmları tek komutla temizleme.
   - `/alert delete`: ID ile alarm iptali.
   - `/price`: Herhangi bir varlığın anlık piyasa değerini sorgulama.
   - `/watchlist show`: Kişisel portföyünüzün anlık değerlerini tek ekranda görme.
   - `/watchlist add` & `/watchlist remove`: Portföy yönetimi.
   - `/help`: Kategori bazlı interaktif yardım menüsü (Genel Rehber, Komutlar, Semboller, TradingView Kurulumu).
   - `/stats`: Bot gecikmesi (ping), çalışma süresi (uptime), aktif alarmlar ve piyasa besleme sağlığı.
4. **İnteraktif Butonlar & Modallar**:
   - Alarm tetiklendiğinde mesaj altında **"🔄 Yeniden Kur"** ve **"🗑 Kapat"** butonları belirir.
   - "Yeniden Kur" butonuna tıklandığında açılan Discord Modal penceresi üzerinden yeni hedef fiyat veya yüzde girilerek alarm anında güncellenebilir.
5. **Kişisel & Sistem Kota Koruması**:
   - Sunucu kaynaklarını korumak için sistem genelinde (`MAX_ACTIVE_ALERTS=100`) ve kullanıcı başına (`MAX_USER_ACTIVE_ALERTS=25`) kota koruması.
   - Unutulan eski alarmlar için otomatik son kullanma temizleyicisi (`ALERT_EXPIRY_DAYS=180`).
6. **Esnek TradingView Webhook Köprüsü**:
   - TradingView Pine Script veya alarm mesajlarını (`/webhook/{token}`) üzerinden karşılar.
   - Eğer `DISCORD_WEBHOOK_URL` tanımlanmamışsa, TradingView sinyallerini otomatik olarak aktif Discord Botu üzerinden hedeflenen kanala iletir!
7. **Dayanıklı SQLite Veritabanı**:
   - `aiosqlite` ile WAL modunda çalışan (`alerts.db`), konteyner güncellemelerinde veri kaybını önleyen kalıcı depolama.

---

## 🎮 Discord Bot Komut Tablosu

| Komut | Açıklama | Örnek Kullanım |
| :--- | :--- | :--- |
| `/alert set <symbol> <target> [note] [dm]` | Yeni fiyat alarmı kurar (fiyat veya yüzde kabul eder) | `/alert set symbol:BTC target_price:+5% note:Direnç dm:True` |
| `/alert list [status]` | Alarmlarınızı canlı fiyat ve kalan fark % ile listeler | `/alert list status:Aktif Alarmlar` |
| `/alert clear [scope]` | Tetiklenmiş veya tüm alarmlarınızı topluca temizler | `/alert clear scope:Sadece Tetiklenmiş Alarmları Temizle` |
| `/alert delete <alert_id>` | Belirli bir alarmı ID ile iptal eder | `/alert delete alert_id:4` |
| `/price <symbol>` | Anlık fiyat sorgular (Autocomplete destekli) | `/price symbol:GOLD` veya `/price symbol:THYAO` |
| `/watchlist show` | Kişisel takip listenizdeki tüm varlıkların anlık fiyatlarını gösterir | `/watchlist show` |
| `/watchlist add <symbol>` | Takip listenize yeni bir sembol ekler | `/watchlist add symbol:SOL` |
| `/watchlist remove <symbol>`| Takip listenizden bir sembolü kaldırır | `/watchlist remove symbol:SOL` |
| `/help` | İnteraktif açılır menülü detaylı yardım rehberi | `/help` |
| `/stats` | Sistem gecikmesi (ping), uptime ve alarm istatistikleri | `/stats` |

---

## 📈 Desteklenen Semboller ve Yazım Formatları

Sistem kullanıcı dostu akıllı sembol ayrıştırıcısına (`symbols.py`) sahiptir. Discord'da arama yaparken otomatik tamamlama listesinden seçim yapabilir veya doğrudan kısaltmasını yazabilirsiniz:

* **🪙 Kripto Paralar (Binance Spot):** `BTC`, `ETH`, `SOL`, `PEPE`, `SUI`, `AVAX`, `DOGE`, `TON`, `RENDER`, `TAO`, `NEAR`, `ARB`, `OP`, `TIA`, `INJ` vb. (Doğrudan kısaltma yeterlidir, otomatik `*USDT` olarak eşlenir).
* **🇹🇷 Borsa İstanbul (100+ BIST Hissesi):** `THYAO`, `ASELS`, `GARAN`, `EREGL`, `SISE`, `KCHOL`, `TUPRS`, `ASTOR`, `REEDR`, `MIATK`, `EUPWR`, `CCOLA`, `MAVI`, `BIMAS` vb. (Sonuna `.IS` yazmanız gerekmez).
* **🏆 Emtialar (Commodities):**
  * `GOLD` veya `ALTIN` (Ons Altın Futures: `GC=F`)
  * `SILVER` veya `GUMUS` (Ons Gümüş Futures: `SI=F`)
  * `BRENT` (Brent Petrol: `BZ=F`)
  * `OIL` veya `WTI` (ABD Ham Petrol: `CL=F`)
  * `NATGAS` veya `DOGALGAZ` (Doğal Gaz: `NG=F`)
  * `COPPER` veya `BAKIR` (`HG=F`), `PLATINUM` (`PL=F`), `COFFEE`, `WHEAT`
* **🌐 Dünya Endeksleri:**
  * `NASDAQ` (Nasdaq 100 Endeksi: `^NDX`), `NQ` (E-mini Nasdaq Vadeli: `NQ=F`)
  * `DJI`, `DOW`, `US30` (Dow Jones 30 Endeksi: `^DJI`), `YM` (Dow Jones Vadeli: `YM=F`)
  * `SP500`, `SPX` (S&P 500: `^GSPC`), `ES` (S&P 500 Vadeli: `ES=F`)
  * `DAX` / `GER40` (`^GDAXI`), `FTSE` / `UK100` (`^FTSE`), `VIX` (Korku Endeksi), `DXY` (Dolar Endeksi)
  * `XU100` (BIST 100), `XU030` (BIST 30), `XBANK` (Bankacılık), `XUSIN` (Sınai)
* **💱 Döviz & Forex Kurları:** `USDTRY`, `EURTRY`, `GBPTRY`, `EURUSD`, `GBPUSD`, `USDJPY` vb. (Otomatik `=X` eklenir).
* **🇺🇸 ABD Dev Şirketleri:** `NVDA`, `AAPL`, `TSLA`, `MSFT`, `AMZN`, `GOOGL`, `META`, `NFLX`, `AMD`, `PLTR`, `COIN`, `MSTR`

---

## 🔔 TradingView Webhook Kurulumu

TradingView grafik veya Pine Script stratejilerinizden botunuza sinyal göndermek için:

1. **Webhook URL:**
   ```text
   https://sizin-coolify-domaininiz.com/webhook/GIZLI_TOKENINIZ
   ```
2. **Alarm Mesajı (JSON Formatı):**
   ```json
   {
     "ticker": "{{ticker}}",
     "action": "{{strategy.order.action}}",
     "price": {{close}},
     "strategy": "Trend Takip 15m",
     "timeframe": "{{interval}}",
     "message": "Kesişim sinyali onaylandı!"
   }
   ```
3. **Düz Metin Formatı:**
   Dilerseniz TradingView mesajına doğrudan `BTCUSDT BUY 68500 Direnç Kırılımı` da yazabilirsiniz.

---

## 🚀 Coolify & Docker Dağıtımı

### 1. Discord Bot Token Alma
1. [Discord Developer Portal](https://discord.com/developers/applications) adresine gidin.
2. **New Application** -> **Bot** sekmesine geçin.
3. **Privileged Gateway Intents** altında **Message Content Intent** seçeneğini açın.
4. **Reset Token** butonuna basarak bot tokeninizi kopyalayın (`DISCORD_BOT_TOKEN`).
5. **OAuth2 -> URL Generator** kısmında `bot` ve `applications.commands` seçin. İzin olarak `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History` verin.
6. Üretilen davet linkiyle botu sunucunuza ekleyin.

### 2. Coolify Ortam Değişkenleri (.env)
Coolify üzerinde aşağıdaki değişkenleri tanımlayın:

```env
# Bot ve Kanal Ayarları
DISCORD_BOT_TOKEN=buraya_bot_tokeniniz
DISCORD_ALERT_CHANNEL_ID=alarmlarin_duyurulacagi_kanal_id
DISCORD_PROXY=http://warp:1080

# Sistem ve Kullanıcı Kotaları
MAX_ACTIVE_ALERTS=100
MAX_USER_ACTIVE_ALERTS=25
ALERT_EXPIRY_DAYS=180
CACHE_TTL_SECONDS=20.0
SQLITE_DB_PATH=/app/data/alerts.db

# TradingView Webhook Ayarları (İsteğe Bağlı)
WEBHOOK_SECRET=buraya_guclu_bir_sifre_veya_token
# DISCORD_WEBHOOK_URL boş bırakılırsa, TradingView sinyalleri bot üzerinden DISCORD_ALERT_CHANNEL_ID'ye gönderilir!
```

---

## 🧪 Otomatik Testler

Tüm sistem birim ve entegrasyon testleri:

```bash
python -m pytest tests -v
```

```text
======================== 50 passed, 1 warning in 1.43s ========================
```
Authentication, dual parser, token bucket rate limiter, SQLite işlemleri, watchlist, DM bildirimleri, yüzdesel alarmlar, cache tazeliği, sembol sınıflandırması ve tetikleyici motoru dahil **50 testin tamamı %100 yeşildir**.

---

## 📄 Lisans (License)

Bu proje [MIT Lisansı](LICENSE) altında açık kaynak olarak lisanslanmıştır. Detaylar için [`LICENSE`](LICENSE) dosyasına göz atabilirsiniz.
