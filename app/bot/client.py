import logging
import time
from datetime import datetime
from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands
from app.config import Settings
from app.database.db import AlertRecord
from app.market_data.symbols import classify_and_normalize, get_symbol_autocomplete
from app.services.alert_engine import AutonomousAlertEngine

logger = logging.getLogger(__name__)


def format_price(price: Optional[float]) -> str:
    """Format price nicely for both small crypto fractions and large indices."""
    if price is None:
        return "*Alınamadı*"
    if price >= 1000.0:
        return f"${price:,.2f}"
    if price >= 1.0:
        return f"${price:,.4f}"
    return f"${price:.8f}".rstrip("0")


async def symbol_autocomplete_handler(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Provide real-time symbol search suggestions for slash commands."""
    suggestions = get_symbol_autocomplete(current)
    return [app_commands.Choice(name=label, value=val) for label, val in suggestions]


class RearmAlertModal(discord.ui.Modal, title="🔄 Alarmı Yeniden Kur"):
    """Interactive modal allowing the user to set a new target price or percent on rearm."""

    target_price = discord.ui.TextInput(
        label="Hedef Fiyat veya Değişim",
        placeholder="Örn: 72000, 150.5, +5%, -3%, 70k",
        required=True,
        max_length=30,
    )
    note = discord.ui.TextInput(
        label="Hatırlatıcı Not (İsteğe Bağlı)",
        placeholder="Örn: Direnç kırılımı, kâr al...",
        required=False,
        max_length=150,
        style=discord.TextStyle.short,
    )

    def __init__(self, engine: AutonomousAlertEngine, alert: AlertRecord):
        super().__init__()
        self.engine = engine
        self.alert = alert
        self.target_price.default = f"{alert.target_price:g}"
        if alert.note:
            self.note.default = alert.note

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        success, msg, new_record = await self.engine.create_user_alert(
            user_id=str(interaction.user.id),
            user_name=interaction.user.name,
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id) if interaction.guild else None,
            raw_symbol=self.alert.symbol,
            target_price=self.target_price.value.strip(),
            note=self.note.value.strip() or None,
            notify_dm=self.alert.notify_dm,
        )
        if success and new_record:
            await interaction.followup.send(
                f"✅ **{new_record.symbol}** için alarm yeniden aktif edildi!\n"
                f"🎯 **Hedef:** `{format_price(new_record.target_price)}` | 📊 **Yön:** `{new_record.direction}` | 🆔 ID: `#{new_record.id}`",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"❌ Alarm kurulamadı: {msg}", ephemeral=True)


class AlertDeleteDropdown(discord.ui.Select):
    """Dropdown menu to select and delete an alert with a single click."""

    def __init__(self, engine: AutonomousAlertEngine, alerts: List[AlertRecord], user_id: str):
        self.engine = engine
        self.user_id = user_id

        options = []
        for a in alerts[:25]:  # Discord select menu max is 25 items
            options.append(
                discord.SelectOption(
                    label=f"ID #{a.id} • {a.symbol} ({format_price(a.target_price)})",
                    value=str(a.id),
                    description=f"{a.direction} | Başlangıç: {format_price(a.initial_price)}",
                    emoji="🗑",
                )
            )

        super().__init__(
            placeholder="Silmek istediğiniz alarmı seçin...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="select_delete_alert",
        )

    async def callback(self, interaction: discord.Interaction):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Sadece kendi alarmlarınızı silebilirsiniz.", ephemeral=True)
            return

        alert_id = int(self.values[0])
        success = await self.engine.db.cancel_alert(alert_id=alert_id, user_id=self.user_id)
        if success:
            self.disabled = True
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(f"✅ `#{alert_id}` ID'li alarm başarıyla iptal edildi ve silindi.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Alarm silinirken bir hata oluştu veya zaten silinmiş.", ephemeral=True)


class AlertListView(discord.ui.View):
    """View container for /alert list with delete dropdown."""

    def __init__(self, engine: AutonomousAlertEngine, alerts: List[AlertRecord], user_id: str):
        super().__init__(timeout=120)
        active_alerts = [a for a in alerts if a.status == "ACTIVE"]
        if active_alerts:
            self.add_item(AlertDeleteDropdown(engine, active_alerts, user_id))


class AlertActionView(discord.ui.View):
    """Interactive Discord buttons attached to triggered alert messages."""

    def __init__(self, engine: AutonomousAlertEngine, alert: AlertRecord):
        super().__init__(timeout=None)
        self.engine = engine
        self.alert = alert

    @discord.ui.button(label="🔄 Yeniden Kur", style=discord.ButtonStyle.green, custom_id="btn_rearm")
    async def rearm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RearmAlertModal(self.engine, self.alert))

    @discord.ui.button(label="🗑 Kapat", style=discord.ButtonStyle.secondary, custom_id="btn_dismiss")
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)


class HelpCategorySelect(discord.ui.Select):
    """Interactive help dropdown switching between topic embeds."""

    def __init__(self):
        options = [
            discord.SelectOption(label="Genel Bakış & Hızlı Başlangıç", value="overview", emoji="🚀"),
            discord.SelectOption(label="Fiyat Alarmları (/alert)", value="alerts", emoji="🎯"),
            discord.SelectOption(label="Fiyat & Takip Listesi (/price, /watchlist)", value="market", emoji="💰"),
            discord.SelectOption(label="Desteklenen Semboller & Örnekler", value="symbols", emoji="📊"),
            discord.SelectOption(label="TradingView Webhook Entegrasyonu", value="tradingview", emoji="🔔"),
        ]
        super().__init__(placeholder="Bir yardım kategorisi seçin...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        cat = self.values[0]
        if cat == "overview":
            embed = discord.Embed(
                title="🚀 TradingView & Autonomous Market Bot Rehberi",
                description=(
                    "Bu bot; Kripto, Borsa İstanbul (BIST), Emtia (Altın, Petrol), Dünya Endeksleri ve Döviz kurlarını "
                    "7/24 otonom olarak takip eden ve TradingView webhook sinyallerini Discord kanalınıza ileten profesyonel bir asistandır."
                ),
                color=0x00D26A,
            )
            embed.add_field(
                name="⚡ Temel Yetenekler",
                value=(
                    "• **Otonom Fiyat Alarmları:** İstediğiniz fiyata veya yüzdesel değişime (`+5%`, `-3%`) alarm kurun.\n"
                    "• **Zengin Varlık Yelpazesi:** 120+ Kripto, 100+ BIST hissesi, Nasdaq, Dow Jones, Altın, Petrol, Döviz.\n"
                    "• **Kişisel Takip Listesi:** `/watchlist` ile portföyünüzün anlık değerlerini tek ekranda görün.\n"
                    "• **Özel Mesaj (DM) Desteği:** Alarmları sunucu yerine doğrudan özel mesajla alın.\n"
                    "• **TradingView Köprüsü:** Pine Script ve TradingView strateji sinyallerini anında iletin."
                ),
                inline=False,
            )
        elif cat == "alerts":
            embed = discord.Embed(
                title="🎯 Fiyat Alarmı Komutları (/alert)",
                description="İstediğiniz varlık için anlık fiyat takip alarmları oluşturun ve yönetin:",
                color=0x3399FF,
            )
            embed.add_field(
                name="🟢 /alert set",
                value=(
                    "Yeni bir alarm kurar.\n"
                    "• **Fiyat Örnekleri:** `70000`, `150.5`, `310,50`, `70k`\n"
                    "• **Yüzdesel Hedef:** `+5%` (anlık fiyattan %5 yukarı), `-3%` (%3 düşüş)\n"
                    "• **Parametreler:** `symbol`, `target_price`, `note` (isteğe bağlı), `dm: True` (isteğe bağlı)"
                ),
                inline=False,
            )
            embed.add_field(
                name="📋 /alert list",
                value="Kurduğunuz alarmları, anlık piyasa fiyatını ve hedefe olan mesafeyi listeler. Açılır menüden tek tıkla silebilirsiniz.",
                inline=False,
            )
            embed.add_field(
                name="🗑 /alert clear",
                value="Tetiklenmiş eski alarmlarınızı veya tüm alarmlarınızı topluca temizler.",
                inline=False,
            )
            embed.add_field(
                name="❌ /alert delete",
                value="Belirli bir alarmı ID numarasıyla iptal eder (Örn: `/alert delete alert_id:5`).",
                inline=False,
            )
        elif cat == "market":
            embed = discord.Embed(
                title="💰 Fiyat Sorgulama & Takip Listesi",
                color=0xF1C40F,
            )
            embed.add_field(
                name="🔍 /price",
                value=(
                    "Herhangi bir sembolün güncel fiyatını anında sorgular.\n"
                    "• **Örnekler:** `/price symbol:BTC`, `/price symbol:THYAO`, `/price symbol:GOLD`, `/price symbol:NASDAQ`"
                ),
                inline=False,
            )
            embed.add_field(
                name="⭐ /watchlist show",
                value="Kişisel listenizdeki tüm hisse, kripto ve emtiaların güncel fiyatlarını tablo halinde gösterir.",
                inline=False,
            )
            embed.add_field(
                name="➕ /watchlist add & remove",
                value=(
                    "• `/watchlist add symbol:BTC` -> Takip listenize ekler.\n"
                    "• `/watchlist remove symbol:BTC` -> Listenizden çıkarır."
                ),
                inline=False,
            )
        elif cat == "symbols":
            embed = discord.Embed(
                title="📊 Desteklenen Sembol Formatları",
                description="Sembolleri yazarken Discord otomatik tamamlama (Autocomplete) önerilerini kullanabilirsiniz:",
                color=0x9B59B6,
            )
            embed.add_field(
                name="🪙 Kripto Paralar (Binance)",
                value="`BTC`, `ETH`, `SOL`, `PEPE`, `SUI`, `AVAX`, `DOGE`, `TON`, `RENDER`, `TAO`, `NEAR` vb. (Doğrudan kısaltma yeterlidir).",
                inline=False,
            )
            embed.add_field(
                name="🇹🇷 Borsa İstanbul (BIST)",
                value="`THYAO`, `ASELS`, `GARAN`, `EREGL`, `SISE`, `KCHOL`, `TUPRS`, `ASTOR`, `REEDR`, `XU100`, `XU030` vb. (Sonuna `.IS` yazmanız gerekmez).",
                inline=False,
            )
            embed.add_field(
                name="🏆 Emtialar",
                value="`GOLD` veya `ALTIN` (Ons Altın), `SILVER` veya `GUMUS`, `BRENT` (Ham Petrol), `NATGAS` (Doğal Gaz), `COPPER` (Bakır).",
                inline=False,
            )
            embed.add_field(
                name="🌐 Dünya Endeksleri & Döviz",
                value="`NASDAQ`, `DJI` (Dow Jones / US30), `SP500`, `DAX`, `DXY` (Dolar Endeksi), `USDTRY`, `EURTRY`, `EURUSD`.",
                inline=False,
            )
        elif cat == "tradingview":
            embed = discord.Embed(
                title="🔔 TradingView Webhook Kurulumu",
                description="TradingView alarmlarınızı bot üzerinden Discord'a yönlendirmek için:",
                color=0x1E88E5,
            )
            embed.add_field(
                name="1. Webhook URL Formatı",
                value="`https://sizin-coolify-domaininiz.com/webhook/GIZLI_TOKENINIZ`\n*(Veya `?secret=GIZLI_TOKENINIZ` şeklinde)*",
                inline=False,
            )
            embed.add_field(
                name="2. TradingView Alarm Mesajı (JSON Şablonu)",
                value=(
                    "```json\n"
                    "{\n"
                    '  "ticker": "{{ticker}}",\n'
                    '  "action": "{{strategy.order.action}}",\n'
                    '  "price": {{close}},\n'
                    '  "strategy": "SuperTrend 15m",\n'
                    '  "timeframe": "{{interval}}",\n'
                    '  "message": "Kesişim sinyali gerçekleşti!"\n'
                    "}\n"
                    "```"
                ),
                inline=False,
            )
            embed.add_field(
                name="3. Düz Metin Desteği",
                value="JSON kullanmak istemiyorsanız TradingView mesajına doğrudan `BTCUSDT BUY 68500 Kırılım` yazabilirsiniz.",
                inline=False,
            )

        embed.set_footer(text="Daha fazla yardım için /help komutunu tekrar çalıştırabilirsiniz.")
        await interaction.response.edit_message(embed=embed, view=self.view)


class HelpView(discord.ui.View):
    """View containing the help category dropdown."""

    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(HelpCategorySelect())


class DiscordAlertBot(commands.Bot):
    """Discord Bot implementation handling Slash Commands, Autocomplete, Watchlist, and Notifications."""

    def __init__(self, engine: AutonomousAlertEngine, settings: Settings):
        intents = discord.Intents.default()
        proxy_url = (settings.DISCORD_PROXY or "").strip() or None
        super().__init__(command_prefix="!", intents=intents, proxy=proxy_url)
        self.engine = engine
        self.settings = settings
        self.start_time = time.time()
        self.engine.trigger_callback = self.dispatch_alert_notification
        if proxy_url:
            logger.info("Discord Bot configured with outbound proxy: %s", proxy_url)

    async def setup_hook(self) -> None:
        """Register slash command groups and sync tree."""
        self._register_commands()
        self._setup_error_handler()
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d Discord Slash Commands.", len(synced))
        except Exception as e:
            logger.warning("Failed syncing slash command tree: %s", e)

    def _setup_error_handler(self) -> None:
        """Global error handler for slash commands."""
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
            logger.error("Error executing command %s: %s", interaction.command.name if interaction.command else "unknown", error, exc_info=True)
            msg = f"⚠️ Komut işlenirken bir hata oluştu: {error}"
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except Exception:
                pass

    async def on_ready(self) -> None:
        """Invoked when bot successfully logs into Discord Gateway and goes Online."""
        logger.info("🚀 Discord Bot is ONLINE! Logged in as: %s (ID: %s)", self.user, self.user.id if self.user else "N/A")
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="Piyasalar | /alert | /help",
                ),
                status=discord.Status.online,
            )
        except Exception as e:
            logger.debug("Failed updating presence activity: %s", e)

    def _register_commands(self) -> None:
        """Define all slash commands and command groups."""
        alert_group = app_commands.Group(name="alert", description="Fiyat alarmı kurma, listeleme ve yönetme komutları")
        watchlist_group = app_commands.Group(name="watchlist", description="Kişisel varlık takip listesi komutları")

        # --- /alert set ---
        @alert_group.command(name="set", description="Yeni bir fiyat alarmı kurar (Kripto, BIST, Altın, Döviz, Endeks)")
        @app_commands.describe(
            symbol="İşlem çifti veya sembol (Örn: BTC, THYAO, USDTRY, NASDAQ, GOLD)",
            target_price="Hedef fiyat veya yüzde (Örn: 70000, 150.5, +5%, -3%, 70k)",
            note="Alarm için isteğe bağlı hatırlatıcı not",
            dm="Tetiklendiğinde doğrudan özel mesaj (DM) ile bildirilsin mi? (Varsayılan: Hayır)",
        )
        @app_commands.autocomplete(symbol=symbol_autocomplete_handler)
        async def set_alert(
            interaction: discord.Interaction,
            symbol: str,
            target_price: str,
            note: Optional[str] = None,
            dm: Optional[bool] = False,
        ):
            await interaction.response.defer(ephemeral=False)
            success, msg, record = await self.engine.create_user_alert(
                user_id=str(interaction.user.id),
                user_name=interaction.user.name,
                channel_id=str(interaction.channel_id),
                guild_id=str(interaction.guild_id) if interaction.guild else None,
                raw_symbol=symbol,
                target_price=target_price,
                note=note,
                notify_dm=bool(dm),
            )

            if not success or not record:
                await interaction.followup.send(f"❌ {msg}")
                return

            direction_tr = "🟢 Yükseliş Kırılımı (ABOVE)" if record.direction == "ABOVE" else "🔴 Düşüş Kırılımı (BELOW)"
            dm_badge = " • 📬 DM Bildirimi Aktif" if record.notify_dm else ""
            pct_distance = ((record.target_price - record.initial_price) / record.initial_price) * 100

            embed = discord.Embed(
                title=f"🎯 Alarm Kuruldu: {record.symbol}",
                color=0x00FF88 if record.direction == "ABOVE" else 0xFF3366,
                timestamp=datetime.fromisoformat(record.created_at),
            )
            embed.add_field(name="💵 Güncel Fiyat", value=f"`{format_price(record.initial_price)}`", inline=True)
            embed.add_field(
                name="🎯 Hedef Fiyat",
                value=f"`{format_price(record.target_price)}` (`{pct_distance:+.2f}%`)",
                inline=True,
            )
            embed.add_field(name="📊 Beklenen Yön", value=f"`{direction_tr}`", inline=False)
            if record.note:
                embed.add_field(name="📝 Not", value=f"> {record.note}", inline=False)
            embed.set_footer(text=f"Alarm ID: #{record.id} • {record.asset_type}{dm_badge}")

            await interaction.followup.send(content=f"{interaction.user.mention}", embed=embed)

        # --- /alert list ---
        @alert_group.command(name="list", description="Kurduğunuz alarmları listeler ve tek tıkla silme menüsü sunar")
        @app_commands.describe(status="Listelenecek alarm durumu (Varsayılan: Sadece aktifler)")
        @app_commands.choices(status=[
            app_commands.Choice(name="🟢 Aktif Alarmlar", value="ACTIVE"),
            app_commands.Choice(name="⚡ Tetiklenmiş Alarmlar", value="TRIGGERED"),
            app_commands.Choice(name="📋 Tüm Alarmlar", value="ALL"),
        ])
        async def list_alerts(interaction: discord.Interaction, status: Optional[str] = "ACTIVE"):
            await interaction.response.defer(ephemeral=True)
            filter_status = None if status == "ALL" else status
            alerts = await self.engine.db.get_user_alerts(user_id=str(interaction.user.id), status=filter_status)

            if not alerts:
                await interaction.followup.send("📭 Bu kategoride kayıtlı alarmınız bulunmamaktadır.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"📋 Alarmlarınız ({len(alerts)} adet)",
                color=0x3399FF,
            )

            for a in alerts[:15]:
                status_icon = "🟢" if a.status == "ACTIVE" else ("⚡" if a.status == "TRIGGERED" else "⚪")
                arrow = "⬆️" if a.direction == "ABOVE" else "⬇️"
                note_str = f"\n> 📝 *{a.note}*" if a.note else ""
                dm_str = " 📬" if a.notify_dm else ""

                current_price = await self.engine.feed.get_current_price(a.symbol)
                if current_price is not None and a.status == "ACTIVE":
                    pct_distance = ((a.target_price - current_price) / current_price) * 100
                    dist_str = f" (Fark: `{pct_distance:+.2f}%`)"
                    price_line = f"Anlık: `{format_price(current_price)}`{dist_str} | Başlangıç: `{format_price(a.initial_price)}`"
                else:
                    price_line = f"Başlangıç: `{format_price(a.initial_price)}`"

                embed.add_field(
                    name=f"{status_icon} ID `#{a.id}`: {a.symbol} {arrow} `{format_price(a.target_price)}`{dm_str}",
                    value=f"Durum: `{a.status}` | {price_line}{note_str}",
                    inline=False,
                )

            if len(alerts) > 15:
                embed.set_footer(text=f"İlk 15 alarm listeleniyor. Toplam: {len(alerts)}")

            view = AlertListView(self.engine, alerts, str(interaction.user.id))
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        # --- /alert clear ---
        @alert_group.command(name="clear", description="Geçmiş veya tüm alarmlarınızı topluca temizler")
        @app_commands.describe(scope="Temizlenecek alarm türü (Varsayılan: Sadece tetiklenmişler)")
        @app_commands.choices(scope=[
            app_commands.Choice(name="⚡ Sadece Tetiklenmiş Alarmları Temizle", value="TRIGGERED"),
            app_commands.Choice(name="🟢 Sadece Aktif Alarmları İptal Et", value="ACTIVE"),
            app_commands.Choice(name="💥 TÜM Alarmlarımı Temizle (Aktif + Tetiklenmiş)", value="ALL"),
        ])
        async def clear_alerts(interaction: discord.Interaction, scope: Optional[str] = "TRIGGERED"):
            await interaction.response.defer(ephemeral=True)
            deleted_count = await self.engine.db.clear_user_alerts(user_id=str(interaction.user.id), status=scope)
            if deleted_count > 0:
                scope_tr = "Tetiklenmiş" if scope == "TRIGGERED" else ("Aktif" if scope == "ACTIVE" else "Tüm")
                await interaction.followup.send(f"🗑 **{deleted_count}** adet {scope_tr} alarm başarıyla temizlendi.", ephemeral=True)
            else:
                await interaction.followup.send("ℹ️ Temizlenecek uygun alarm bulunamadı.", ephemeral=True)

        # --- /alert delete ---
        @alert_group.command(name="delete", description="Belirli bir alarmı ID ile iptal eder")
        @app_commands.describe(alert_id="İptal edilecek alarm ID'si (Örn: 5)")
        async def delete_alert(interaction: discord.Interaction, alert_id: int):
            await interaction.response.defer(ephemeral=True)
            success = await self.engine.db.cancel_alert(alert_id=alert_id, user_id=str(interaction.user.id))
            if success:
                await interaction.followup.send(f"🗑 ID `#{alert_id}` numaralı alarm iptal edildi.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ `#{alert_id}` ID'li aktif bir alarmınız bulunamadı.", ephemeral=True)

        # --- /price ---
        @self.tree.command(name="price", description="Herhangi bir sembolün güncel fiyatını sorgular")
        @app_commands.describe(symbol="Sorgulanacak sembol (Örn: BTC, ETH, THYAO, GOLD, NASDAQ, DJI, USDTRY)")
        @app_commands.autocomplete(symbol=symbol_autocomplete_handler)
        async def price_query(interaction: discord.Interaction, symbol: str):
            await interaction.response.defer(ephemeral=False)
            norm_symbol, _ = classify_and_normalize(symbol)
            current_price = await self.engine.feed.get_current_price(symbol)
            if current_price is None:
                await interaction.followup.send(f"❌ **{symbol}** için anlık fiyat alınamadı.")
                return

            display_title = symbol.upper().strip()
            if display_title != norm_symbol:
                display_title = f"{display_title} ({norm_symbol})"

            embed = discord.Embed(
                title=f"💰 Fiyat Bilgisi: {display_title}",
                color=0x3399FF,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Anlık Değer", value=f"`{format_price(current_price)}`", inline=True)
            await interaction.followup.send(embed=embed)

        # --- /watchlist show ---
        @watchlist_group.command(name="show", description="Kişisel takip listenizdeki tüm varlıkların anlık fiyatlarını gösterir")
        async def watchlist_show(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)
            symbols = await self.engine.db.get_user_watchlist(str(interaction.user.id))

            if not symbols:
                await interaction.followup.send(
                    "📭 Takip listeniz boş! `/watchlist add symbol:BTC` komutu ile semboller ekleyebilirsiniz.",
                    ephemeral=True,
                )
                return

            embed = discord.Embed(
                title="⭐ Kişisel Takip Listeniz",
                description="Listenizdeki varlıkların güncel anlık fiyatları:",
                color=0xF1C40F,
                timestamp=datetime.now(),
            )

            for sym in symbols:
                price = await self.engine.feed.get_current_price(sym)
                embed.add_field(name=f"🔹 {sym}", value=f"`{format_price(price)}`", inline=True)

            embed.set_footer(text=f"Toplam: {len(symbols)} varlık • /watchlist")
            await interaction.followup.send(embed=embed)

        # --- /watchlist add ---
        @watchlist_group.command(name="add", description="Takip listenize yeni bir sembol ekler")
        @app_commands.describe(symbol="Takip listesine eklenecek sembol (Örn: BTC, ETH, THYAO, GOLD)")
        @app_commands.autocomplete(symbol=symbol_autocomplete_handler)
        async def watchlist_add(interaction: discord.Interaction, symbol: str):
            await interaction.response.defer(ephemeral=True)
            norm_symbol, asset_type = classify_and_normalize(symbol)
            success = await self.engine.db.add_to_watchlist(str(interaction.user.id), norm_symbol, asset_type)

            if success:
                price = await self.engine.feed.get_current_price(norm_symbol)
                price_info = f" (Anlık: `{format_price(price)}`)" if price is not None else ""
                await interaction.followup.send(
                    f"⭐ **{norm_symbol}** takip listenize eklendi!{price_info}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    f"ℹ️ **{norm_symbol}** zaten takip listenizde kayıtlı.",
                    ephemeral=True,
                )

        # --- /watchlist remove ---
        @watchlist_group.command(name="remove", description="Takip listenizden bir sembolü kaldırır")
        @app_commands.describe(symbol="Kaldırılacak sembol")
        @app_commands.autocomplete(symbol=symbol_autocomplete_handler)
        async def watchlist_remove(interaction: discord.Interaction, symbol: str):
            await interaction.response.defer(ephemeral=True)
            norm_symbol, _ = classify_and_normalize(symbol)
            success = await self.engine.db.remove_from_watchlist(str(interaction.user.id), norm_symbol)

            if success:
                await interaction.followup.send(f"🗑 **{norm_symbol}** takip listenizden çıkarıldı.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ **{norm_symbol}** takip listenizde bulunamadı.", ephemeral=True)

        # --- /help ---
        @self.tree.command(name="help", description="Bot özellikleri, komutlar ve sembol kullanım rehberi")
        async def help_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            embed = discord.Embed(
                title="📖 TradingView & Market Alert Bot Rehberi",
                description=(
                    "Aşağıdaki açılır menüden ilgilendiğiniz kategoriyi seçerek detaylı bilgi edinebilirsiniz:\n\n"
                    "• 🚀 **Genel Bakış & Hızlı Başlangıç**\n"
                    "• 🎯 **Fiyat Alarmları (`/alert`)**\n"
                    "• 💰 **Fiyat & Takip Listesi (`/price`, `/watchlist`)**\n"
                    "• 📊 **Desteklenen Semboller & Örnekler**\n"
                    "• 🔔 **TradingView Webhook Entegrasyonu**"
                ),
                color=0x00D26A,
            )
            embed.set_footer(text="Bir kategori seçmek için aşağıdaki menüyü kullanın.")
            view = HelpView()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        # --- /stats ---
        @self.tree.command(name="stats", description="Sistem durumu, gecikme süresi, aktif alarm sayıları ve istatistikler")
        async def stats_command(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=False)
            db_stats = await self.engine.db.get_database_stats()
            uptime_seconds = int(time.time() - self.start_time)
            uptime_hours, rem = divmod(uptime_seconds, 3600)
            uptime_mins, uptime_secs = divmod(rem, 60)

            latency_ms = round(self.latency * 1000, 1) if self.latency else 0.0

            embed = discord.Embed(
                title="📊 Sistem ve Bot İstatistikleri",
                color=0x3399FF,
                timestamp=datetime.now(),
            )
            embed.add_field(name="🏓 Ağ Gecikmesi (Ping)", value=f"`{latency_ms} ms`", inline=True)
            embed.add_field(name="⏱ Çalışma Süresi (Uptime)", value=f"`{uptime_hours}s {uptime_mins}d {uptime_secs}sn`", inline=True)
            embed.add_field(name="🟢 Aktif Alarmlar", value=f"`{db_stats['active_alerts']}` adet", inline=True)
            embed.add_field(name="⚡ Tetiklenmiş Alarmlar", value=f"`{db_stats['triggered_alerts']}` adet", inline=True)
            embed.add_field(name="⭐ Takip Listesi Varlıkları", value=f"`{db_stats['watchlist_items']}` adet", inline=True)
            embed.add_field(name="🌐 Piyasa Beslemesi", value="`Binance WS + Yahoo Poller`", inline=True)
            embed.set_footer(text="TradingView Price Alert & Market Engine")

            await interaction.followup.send(embed=embed)

        self.tree.add_command(alert_group)
        self.tree.add_command(watchlist_group)

    async def dispatch_alert_notification(self, alert: AlertRecord, current_price: float) -> None:
        """Send rich embed notification to target channel or directly via DM."""
        is_bullish = alert.direction == "ABOVE"
        direction_label = "Yükseliş Kırılımı (ABOVE)" if is_bullish else "Düşüş Kırılımı (BELOW)"
        color = 0x00FF88 if is_bullish else 0xFF3366
        icon = "🚀" if is_bullish else "⚠️"
        pct_change = ((current_price - alert.initial_price) / alert.initial_price) * 100

        embed = discord.Embed(
            title=f"{icon} FİYAT ALARMI TETİKLENDİ: {alert.symbol}",
            description=f"> **{alert.symbol}** hedef fiyata ulaştı! (`{pct_change:+.2f}%`)",
            color=color,
            timestamp=datetime.now(),
        )
        embed.add_field(name="🎯 Hedef Fiyat", value=f"`{format_price(alert.target_price)}`", inline=True)
        embed.add_field(name="⚡ Tetiklenme Fiyatı", value=f"`{format_price(current_price)}`", inline=True)
        embed.add_field(name="💵 Başlangıç Fiyatı", value=f"`{format_price(alert.initial_price)}`", inline=True)
        embed.add_field(name="📊 Hareket Yönü", value=f"`{direction_label}`", inline=False)

        if alert.note:
            embed.add_field(name="📝 Hatırlatıcı Not", value=f"> {alert.note}", inline=False)

        embed.set_footer(text=f"Alarm ID: #{alert.id} • Coolify Alert Engine")
        view = AlertActionView(self.engine, alert)
        content = f"<@{alert.user_id}>"

        # 1. If notify_dm is requested, attempt Direct Message dispatch first
        if alert.notify_dm:
            try:
                user = self.get_user(int(alert.user_id)) or await self.fetch_user(int(alert.user_id))
                if user:
                    await user.send(content="🔔 **Fiyat Alarmınız Tetiklendi!**", embed=embed, view=view)
                    logger.info("Successfully dispatched DM alert #%d to user %s", alert.id, alert.user_id)
                    return
            except Exception as dm_err:
                logger.warning("Failed sending DM to user %s (falling back to channel): %s", alert.user_id, dm_err)

        # 2. Standard Channel dispatch
        target_channel_id = self.settings.DISCORD_ALERT_CHANNEL_ID or int(alert.channel_id)
        channel = self.get_channel(target_channel_id)

        if not channel:
            try:
                channel = await self.fetch_channel(target_channel_id)
            except Exception as e:
                logger.error("Could not fetch Discord channel %s to dispatch alert: %s", target_channel_id, e)
                return

        try:
            await channel.send(content=content, embed=embed, view=view)
            logger.info("Successfully announced alert #%d in Discord channel %s", alert.id, target_channel_id)
        except Exception as e:
            logger.error("Failed to send alert message to Discord channel: %s", e, exc_info=True)
