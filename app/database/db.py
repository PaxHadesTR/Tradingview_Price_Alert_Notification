import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class AlertRecord:
    id: int
    user_id: str
    user_name: str
    channel_id: str
    guild_id: Optional[str]
    symbol: str
    asset_type: str  # "CRYPTO" or "EQUITY_FOREX"
    target_price: float
    initial_price: float
    direction: str  # "ABOVE" or "BELOW"
    status: str  # "ACTIVE", "TRIGGERED", "CANCELLED", "EXPIRED"
    created_at: str
    triggered_at: Optional[str] = None
    note: Optional[str] = None
    notify_dm: bool = False

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"


class AlertDatabase:
    """Asynchronous SQLite manager for user alerts with WAL mode and atomic state transitions."""

    def __init__(self, db_path: str = "./data/alerts.db") -> None:
        self.db_path = db_path

    async def init_db(self) -> None:
        """Create tables and performance indexes with WAL mode."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    guild_id TEXT,
                    symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    target_price REAL NOT NULL,
                    initial_price REAL NOT NULL,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    triggered_at TEXT,
                    note TEXT,
                    notify_dm INTEGER DEFAULT 0
                );
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status_symbol ON alerts(status, symbol);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_user_status ON alerts(user_id, status);")

            # Migration check: Ensure notify_dm column exists
            async with db.execute("PRAGMA table_info(alerts);") as cursor:
                columns = [row[1] for row in await cursor.fetchall()]
                if "notify_dm" not in columns:
                    await db.execute("ALTER TABLE alerts ADD COLUMN notify_dm INTEGER DEFAULT 0;")

            # Watchlist Table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, symbol)
                );
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);")
            await db.commit()
            logger.info("Initialized alerts & watchlist database at %s", self.db_path)

    async def add_alert(
        self,
        user_id: str,
        user_name: str,
        channel_id: str,
        guild_id: Optional[str],
        symbol: str,
        asset_type: str,
        target_price: float,
        initial_price: float,
        direction: str,
        note: Optional[str] = None,
        notify_dm: bool = False,
    ) -> int:
        """Insert a new active alert and return its generated ID."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO alerts (
                    user_id, user_name, channel_id, guild_id,
                    symbol, asset_type, target_price, initial_price,
                    direction, status, created_at, note, notify_dm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?);
                """,
                (
                    user_id,
                    user_name,
                    channel_id,
                    guild_id,
                    symbol.upper().strip(),
                    asset_type.upper().strip(),
                    target_price,
                    initial_price,
                    direction.upper().strip(),
                    now_iso,
                    note.strip() if note else None,
                    1 if notify_dm else 0,
                ),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_active_alerts(self, symbol: Optional[str] = None) -> List[AlertRecord]:
        """Fetch active alerts, optionally filtered by symbol."""
        query = "SELECT * FROM alerts WHERE status = 'ACTIVE'"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol.upper().strip())

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_record(row) for row in rows]

    async def get_user_alerts(self, user_id: str, status: Optional[str] = None) -> List[AlertRecord]:
        """Fetch alerts belonging to a specific Discord user."""
        query = "SELECT * FROM alerts WHERE user_id = ?"
        params = [user_id]
        if status:
            query += " AND status = ?"
            params.append(status.upper().strip())
        query += " ORDER BY id DESC"

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_record(row) for row in rows]

    async def get_alert_by_id(self, alert_id: int) -> Optional[AlertRecord]:
        """Retrieve a specific alert by primary key ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)) as cursor:
                row = await cursor.fetchone()
                return self._row_to_record(row) if row else None

    async def trigger_alert(self, alert_id: int) -> bool:
        """Atomically transition alert status from ACTIVE to TRIGGERED."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE alerts
                SET status = 'TRIGGERED', triggered_at = ?
                WHERE id = ? AND status = 'ACTIVE';
                """,
                (now_iso, alert_id),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def cancel_alert(self, alert_id: int, user_id: Optional[str] = None) -> bool:
        """Cancel an active alert. If user_id provided, ensures user owns the alert."""
        query = "UPDATE alerts SET status = 'CANCELLED' WHERE id = ? AND status = 'ACTIVE'"
        params = [alert_id]
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor.rowcount > 0

    async def count_active_alerts(self, user_id: Optional[str] = None) -> int:
        """Count currently active alerts in the database."""
        query = "SELECT COUNT(*) FROM alerts WHERE status = 'ACTIVE'"
        params = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def expire_stale_alerts(self, max_age_days: int = 180) -> int:
        """Find and expire active alerts older than max_age_days."""
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                UPDATE alerts
                SET status = 'EXPIRED'
                WHERE status = 'ACTIVE' AND created_at < ?;
                """,
                (cutoff_date,),
            )
            await db.commit()
            if cursor.rowcount > 0:
                logger.info("Expired %d stale alerts older than %d days.", cursor.rowcount, max_age_days)
            return cursor.rowcount

    # --- Watchlist Methods ---
    async def add_to_watchlist(self, user_id: str, symbol: str, asset_type: str) -> bool:
        """Add symbol to user's personal watchlist."""
        now_iso = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO watchlist (user_id, symbol, asset_type, created_at)
                    VALUES (?, ?, ?, ?);
                    """,
                    (user_id, symbol.upper().strip(), asset_type.upper().strip(), now_iso),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def remove_from_watchlist(self, user_id: str, symbol: str) -> bool:
        """Remove symbol from user's watchlist."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM watchlist WHERE user_id = ? AND symbol = ?;",
                (user_id, symbol.upper().strip()),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def get_user_watchlist(self, user_id: str) -> List[str]:
        """Fetch list of symbols on user's watchlist."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT symbol FROM watchlist WHERE user_id = ? ORDER BY id ASC;",
                (user_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [r[0] for r in rows]

    def _row_to_record(self, row: aiosqlite.Row) -> AlertRecord:
        notify_dm_val = False
        try:
            notify_dm_val = bool(row["notify_dm"])
        except (IndexError, KeyError):
            pass

        return AlertRecord(
            id=row["id"],
            user_id=row["user_id"],
            user_name=row["user_name"],
            channel_id=row["channel_id"],
            guild_id=row["guild_id"],
            symbol=row["symbol"],
            asset_type=row["asset_type"],
            target_price=row["target_price"],
            initial_price=row["initial_price"],
            direction=row["direction"],
            status=row["status"],
            created_at=row["created_at"],
            triggered_at=row["triggered_at"],
            note=row["note"],
            notify_dm=notify_dm_val,
        )
