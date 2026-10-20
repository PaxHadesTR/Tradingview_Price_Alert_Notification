import logging
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


async def symbol_autocomplete_handler(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    """Provide real-time symbol search suggestions for slash commands."""
    suggestions = get_symbol_autocomplete(current)
    return [app_commands.Choice(name=label, value=val) for label, val in suggestions]


class AlertDeleteDropdown(discord.ui.Select):
    """Dropdown menu to select and delete an alert with a single click."""

    def __init__(self, engine: AutonomousAlertEngine, alerts: List[AlertRecord], user_id: str):
        self.engine = engine
        self.user_id = user_id

        options = []
        for a in alerts[:25]:  # Discord select menu max is 25 items
            options.append(
                discord.SelectOption(
                    label=f"ID #{a.id} • {a.symbol} (${a.target_price:,.4f})",
                    value=str(a.id),
                    description=f"{a.direction} | Başlangıç: ${a.initial_price:,.4f}",
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
        success, msg, new_record = await self.engine.create_user_alert(
            user_id=str(interaction.user.id),
            user_name=interaction.user.name,
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id) if interaction.guild else None,
            raw_symbol=self.alert.symbol,
            target_price=self.alert.target_price,
            note=self.alert.note,
            notify_dm=self.alert.notify_dm,
        )
        if success and new_record:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"✅ **{self.alert.symbol}** için alarm yeniden aktif edildi! (ID: `#{new_record.id}`, Hedef: `${new_record.target_price:,.4f}`)",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(f"❌ Yeniden kurulamadı: {msg}", ephemeral=True)

    @discord.ui.button(label="🗑 Temizle", style=discord.ButtonStyle.secondary, custom_id="btn_dismiss")
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)


class DiscordAlertBot(commands.Bot):
    """Discord Bot implementation handling Slash Commands, Autocomplete, Watchlist, and Notifications."""

    def __init__(self, engine: AutonomousAlertEngine, settings: Settings):
        intents = discord.Intents.default()
        proxy_url = (settings.DISCORD_PROXY or "").strip() or None
        super().__init__(command_prefix="!", intents=intents, proxy=proxy_url)
        self.engine = engine
        self.settings = settings
        self.engine.trigger_callback = self.dispatch_alert_notification
        if proxy_url:
            logger.info("Discord Bot configured with outbound proxy: %s", proxy_url)

    async def setup_hook(self) -> None:
        """Register slash command groups and sync tree."""
        self._register_commands()
        try:
            synced = await self.tree.sync()
            logger.info("Synced %d Discord Slash Commands.", len(synced))
        except Exception as e:
            logger.warning("Failed syncing slash command tree (bot might lack permissions or offline): %s", e)

    async def on_ready(self) -> None:
        """Invoked when bot successfully logs into Discord Gateway and goes Online."""
        logger.info("🚀 Discord Bot is ONLINE! Logged in as: %s (ID: %s)", self.user, self.user.id if self.user else "N/A")
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="Piyasalar | /alert",
                ),
                status=discord.Status.online,
            )
        except Exception as e:
            logger.debug("Failed updating presence activity: %s", e)

    def _register_commands(self) -> None:
        """Define all slash commands and command groups."""
        alert_group = app_commands.Group(name="alert", description="Fiyat alarmı komutları")
        watchlist_group = app_commands.Group(name="watchlist", description="Kişisel takip listesi komutları")

        # --- /alert set ---
        @alert_group.command(name="set", description="Yeni bir fiyat alarmı kurar (Kripto, BIST, Hisse, Altın, Döviz)")
        @app_commands.describe(
            symbol="İşlem çifti veya sembol (Örn: BTCUSDT, THYAO, USDTRY, NASDAQ, GOLD)",
            target_price="Alarmın tetikleneceği hedef fiyat",
            note="Alarm için isteğe bağlı hatırlatıcı not",
            dm="Tetiklendiğinde doğrudan özel mesaj (DM) ile bildirilsin mi? (Varsayılan: Hayır)",
        )
        @app_commands.autocomplete(symbol=symbol_autocomplete_handler)
        async def set_alert(
            interaction: discord.Interaction,
            symbol: str,
            target_price: float,
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
            embed = discord.Embed(
                title=f"🎯 Alarm Kuruldu: {record.symbol}",
                color=0x00FF88 if record.direction == "ABOVE" else 0xFF3366,
                timestamp=datetime.fromisoformat(record.created_at),
            )
            embed.add_field(name="💵 Güncel Fiyat", value=f"`${record.initial_price:,.4f}`", inline=True)
            embed.add_field(name="🎯 Hedef Fiyat", value=f"`${record.target_price:,.4f}`", inline=True)
            embed.add_field(name="📊 Beklenen Yön", value=f"`{direction_tr}`", inline=False)
            if record.note:
                embed.add_field(name="📝 Not", value=f"> {record.note}", inline=False)
            embed.set_footer(text=f"Alarm ID: #{record.id} • {record.asset_type}{dm_badge}")

            await interaction.followup.send(content=f"{interaction.user.mention}", embed=embed)

        # --- /alert list ---
        @alert_group.command(name="list", description="Kurduğunuz alarmları listeler ve tek tıkla silme menüsü sunar")
        @app_commands.describe(status="Listelenecek alarm durumu (Varsayılan: Sadece aktifler)")
        @app_commands.choices(status=[
            app_commands.Choice(name="Aktif Alarmlar", value="ACTIVE"),
            app_commands.Choice(name="Tetiklenmiş Alarmlar", value="TRIGGERED"),
            app_commands.Choice(name="Tüm Alarmlar", value="ALL"),
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

                # Fetch live price if active
                current_price = await self.engine.feed.get_current_price(a.symbol)
                if current_price is not None and a.status == "ACTIVE":
                    pct_distance = ((a.target_price - current_price) / current_price) * 100
                    dist_str = f" (Fark: `{pct_distance:+.2f}%`)"
                    price_line = f"Anlık: `${current_price:,.4f}`{dist_str} | Başlangıç: `${a.initial_price:,.4f}`"
                else:
                    price_line = f"Başlangıç: `${a.initial_price:,.4f}`"

                embed.add_field(
                    name=f"{status_icon} ID `#{a.id}`: {a.symbol} {arrow} `${a.target_price:,.4f}`{dm_str}",
                    value=f"Durum: `{a.status}` | {price_line}{note_str}",
                    inline=False,
                )

            if len(alerts) > 15:
                embed.set_footer(text=f"İlk 15 alarm listeleniyor. Toplam: {len(alerts)}")

            view = AlertListView(self.engine, alerts, str(interaction.user.id))
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

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
            embed.add_field(name="Anlık Değer", value=f"`${current_price:,.4f}`", inline=True)
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
                price_str = f"`${price:,.4f}`" if price is not None else "*Fiyat alınamadı*"
                embed.add_field(name=f"🔹 {sym}", value=price_str, inline=True)

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
                price_info = f" (Anlık: `${price:,.4f}`)" if price is not None else ""
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

        self.tree.add_command(alert_group)
        self.tree.add_command(watchlist_group)

    async def dispatch_alert_notification(self, alert: AlertRecord, current_price: float) -> None:
        """Send rich embed notification to target channel or directly via DM."""
        is_bullish = alert.direction == "ABOVE"
        direction_label = "Yükseliş Kırılımı (ABOVE)" if is_bullish else "Düşüş Kırılımı (BELOW)"
        color = 0x00FF88 if is_bullish else 0xFF3366
        icon = "🚀" if is_bullish else "⚠️"

        embed = discord.Embed(
            title=f"{icon} FİYAT ALARMI TETİKLENDİ: {alert.symbol}",
            description=f"> **{alert.symbol}** hedef fiyata ulaştı!",
            color=color,
            timestamp=datetime.now(),
        )
        embed.add_field(name="🎯 Hedef Fiyat", value=f"`${alert.target_price:,.4f}`", inline=True)
        embed.add_field(name="⚡ Tetiklenme Fiyatı", value=f"`${current_price:,.4f}`", inline=True)
        embed.add_field(name="💵 Başlangıç Fiyatı", value=f"`${alert.initial_price:,.4f}`", inline=True)
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
