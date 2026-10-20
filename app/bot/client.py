import logging
from datetime import datetime
from typing import Optional
import discord
from discord import app_commands
from discord.ext import commands
from app.config import Settings
from app.database.db import AlertRecord
from app.services.alert_engine import AutonomousAlertEngine

logger = logging.getLogger(__name__)


class AlertActionView(discord.ui.View):
    """Interactive Discord buttons attached to triggered alert messages."""

    def __init__(self, engine: AutonomousAlertEngine, alert: AlertRecord):
        super().__init__(timeout=None)
        self.engine = engine
        self.alert = alert

    @discord.ui.button(label="🔄 Yeniden Kur", style=discord.ButtonStyle.green, custom_id="btn_rearm")
    async def rearm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Re-create alert with same parameters
        success, msg, new_record = await self.engine.create_user_alert(
            user_id=str(interaction.user.id),
            user_name=interaction.user.name,
            channel_id=str(interaction.channel_id),
            guild_id=str(interaction.guild_id) if interaction.guild else None,
            raw_symbol=self.alert.symbol,
            target_price=self.alert.target_price,
            note=self.alert.note,
        )
        if success and new_record:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"✅ **{self.alert.symbol}** için alarm yeniden aktif edildi! (Alarm ID: `#{new_record.id}`, Hedef: `${new_record.target_price:,.4f}`)",
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
    """Discord Bot implementation handling Slash Commands and alert notifications."""

    def __init__(self, engine: AutonomousAlertEngine, settings: Settings):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.engine = engine
        self.settings = settings
        self.engine.trigger_callback = self.dispatch_alert_notification

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
        """Define slash commands using discord.app_commands."""
        alert_group = app_commands.Group(name="alert", description="Fiyat alarmı komutları")

        @alert_group.command(name="set", description="Yeni bir fiyat alarmı kurar (Kripto, BIST, Hisse, Altın, Döviz)")
        @app_commands.describe(
            symbol="İşlem çifti veya sembol (Örn: BTCUSDT, THYAO, USDTRY, AAPL, GOLD)",
            target_price="Alarmın tetikleneceği hedef fiyat",
            note="Alarm için isteğe bağlı hatırlatıcı not",
        )
        async def set_alert(interaction: discord.Interaction, symbol: str, target_price: float, note: Optional[str] = None):
            await interaction.response.defer(ephemeral=False)
            success, msg, record = await self.engine.create_user_alert(
                user_id=str(interaction.user.id),
                user_name=interaction.user.name,
                channel_id=str(interaction.channel_id),
                guild_id=str(interaction.guild_id) if interaction.guild else None,
                raw_symbol=symbol,
                target_price=target_price,
                note=note,
            )

            if not success or not record:
                await interaction.followup.send(f"❌ {msg}")
                return

            direction_tr = "🟢 Yükseliş Kırılımı (ABOVE)" if record.direction == "ABOVE" else "🔴 Düşüş Kırılımı (BELOW)"
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
            embed.set_footer(text=f"Alarm ID: #{record.id} • {record.asset_type}")

            await interaction.followup.send(content=f"{interaction.user.mention}", embed=embed)

        @alert_group.command(name="list", description="Kurduğunuz alarmları listeler")
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
                note_str = f" - *{a.note}*" if a.note else ""
                embed.add_field(
                    name=f"{status_icon} ID `#{a.id}`: {a.symbol} {arrow} ${a.target_price:,.4f}",
                    value=f"Durum: `{a.status}` | Başlangıç: `${a.initial_price:,.4f}`{note_str}",
                    inline=False,
                )

            if len(alerts) > 15:
                embed.set_footer(text=f"İlk 15 alarm gösteriliyor. Toplam: {len(alerts)}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        @alert_group.command(name="delete", description="Belirli bir alarmı ID ile iptal eder")
        @app_commands.describe(alert_id="İptal edilecek alarm ID'si (Örn: 5)")
        async def delete_alert(interaction: discord.Interaction, alert_id: int):
            await interaction.response.defer(ephemeral=True)
            success = await self.engine.db.cancel_alert(alert_id=alert_id, user_id=str(interaction.user.id))
            if success:
                await interaction.followup.send(f"🗑 ID `#{alert_id}` numaralı alarm iptal edildi.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ `#{alert_id}` ID'li aktif bir alarmınız bulunamadı.", ephemeral=True)

        @self.tree.command(name="price", description="Herhangi bir sembolün güncel fiyatını sorgular")
        @app_commands.describe(symbol="Sorgulanacak sembol (Örn: BTCUSDT, THYAO, USDTRY, AAPL, GOLD)")
        async def price_query(interaction: discord.Interaction, symbol: str):
            await interaction.response.defer(ephemeral=False)
            current_price = await self.engine.feed.get_current_price(symbol)
            if current_price is None:
                await interaction.followup.send(f"❌ **{symbol}** için anlık fiyat alınamadı.")
                return

            embed = discord.Embed(
                title=f"💰 Fiyat Bilgisi: {symbol.upper()}",
                color=0x3399FF,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Anlık Değer", value=f"`${current_price:,.4f}`", inline=True)
            await interaction.followup.send(embed=embed)

        self.tree.add_command(alert_group)

    async def dispatch_alert_notification(self, alert: AlertRecord, current_price: float) -> None:
        """Send rich embed notification to target Discord channel mentioning user."""
        target_channel_id = self.settings.DISCORD_ALERT_CHANNEL_ID or int(alert.channel_id)
        channel = self.get_channel(target_channel_id)

        if not channel:
            try:
                channel = await self.fetch_channel(target_channel_id)
            except Exception as e:
                logger.error("Could not fetch Discord channel %s to dispatch alert: %s", target_channel_id, e)
                return

        # Formatting
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

        try:
            await channel.send(content=content, embed=embed, view=view)
            logger.info("Successfully announced alert #%d in Discord channel %s", alert.id, target_channel_id)
        except Exception as e:
            logger.error("Failed to send alert message to Discord channel: %s", e, exc_info=True)
