"""
Database layer using aiosqlite (async SQLite).
Swap DATABASE_URL to postgres:// + asyncpg for production.
"""
import aiosqlite
import asyncio
import logging
from datetime import datetime, date
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("bot.db")


async def get_db():
    return await aiosqlite.connect(DB_PATH)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            full_name     TEXT,
            plan          TEXT DEFAULT 'free',        -- free | basic | pro
            plan_expires  TEXT,                        -- ISO date or NULL
            searches_today INTEGER DEFAULT 0,
            last_search_date TEXT,
            bonus_searches INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referred_by   INTEGER,
            referral_count INTEGER DEFAULT 0,
            points        INTEGER DEFAULT 0,
            joined_at     TEXT DEFAULT (datetime('now')),
            state         TEXT DEFAULT 'idle',          -- conversation state machine
            currency      TEXT DEFAULT 'EGP',            -- detected from Telegram language_code
            country_name  TEXT DEFAULT 'مصر'
        );

        CREATE TABLE IF NOT EXISTS price_alerts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            product_name  TEXT,
            product_url   TEXT,
            target_price  REAL,
            current_price REAL,
            currency      TEXT DEFAULT 'EGP',
            store         TEXT,
            active        INTEGER DEFAULT 1,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER,
            query         TEXT,
            results_count INTEGER,
            searched_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS referral_rewards (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id   INTEGER,
            referred_id   INTEGER,
            points_earned INTEGER,
            rewarded_at   TEXT DEFAULT (datetime('now'))
        );
        """)
        await db.commit()

        # Lightweight migration: add columns if the DB pre-dates this version
        await _ensure_column(db, "users", "currency", "TEXT DEFAULT 'EGP'")
        await _ensure_column(db, "users", "country_name", "TEXT DEFAULT 'مصر'")
    logger.info("DB tables ready.")


async def _ensure_column(db, table: str, column: str, col_def: str):
    """Adds a column to an existing table if it doesn't already exist (SQLite migration helper)."""
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in await cur.fetchall()]
    if column not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        await db.commit()
        logger.info(f"Migrated: added column '{column}' to '{table}'")


async def set_user_currency(user_id: int, currency: str, country_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET currency=?, country_name=? WHERE user_id=?",
            (currency, country_name, user_id)
        )
        await db.commit()


async def get_user_currency(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT currency FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else "EGP"


# ─── User helpers ─────────────────────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str, full_name: str,
                               language_code: str | None = None) -> dict:
    import random, string
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if row:
            return dict(row)

        # Detect currency from Telegram language_code at creation time only
        currency, country_name = "EGP", "مصر"
        if language_code:
            from utils.currency import LANG_TO_CURRENCY, REGION_OVERRIDES, DEFAULT_CURRENCY
            code = language_code.lower()
            if code in REGION_OVERRIDES:
                currency, country_name = REGION_OVERRIDES[code]
            else:
                currency, country_name = LANG_TO_CURRENCY.get(code.split("-")[0], DEFAULT_CURRENCY)

        # create
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        await db.execute(
            "INSERT INTO users (user_id, username, full_name, referral_code, currency, country_name) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, username, full_name, ref_code, currency, country_name)
        )
        await db.commit()
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return dict(await cur.fetchone())


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def can_search(user_id: int) -> tuple[bool, str]:
    """Returns (allowed, reason). Resets daily counter if new day."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = dict(await cur.fetchone())

    today = date.today().isoformat()
    if user["last_search_date"] != today:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "UPDATE users SET searches_today=0, last_search_date=? WHERE user_id=?",
                (today, user_id)
            )
            await db.commit()
        user["searches_today"] = 0

    from config.settings import settings
    limits = {"free": settings.FREE_SEARCHES_PER_DAY,
              "basic": settings.BASIC_SEARCHES_PER_DAY,
              "pro": settings.PRO_SEARCHES_PER_DAY}
    limit = limits.get(user["plan"], settings.FREE_SEARCHES_PER_DAY)
    bonus = user.get("bonus_searches", 0)
    used = user["searches_today"]

    if used < limit + bonus:
        return True, "ok"
    return False, f"وصلت الحد اليومي ({limit} بحث). ترقّ لخطة أعلى أو استبدل نقاطك 🔒"


async def increment_search_count(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET searches_today = searches_today + 1 WHERE user_id=?",
            (user_id,)
        )
        await db.commit()


async def set_user_state(user_id: int, state: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET state=? WHERE user_id=?", (state, user_id))
        await db.commit()


async def get_user_state(user_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT state FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else "idle"


async def add_points(user_id: int, points: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET points = points + ? WHERE user_id=?", (points, user_id))
        await db.commit()


async def redeem_points(user_id: int, points: int, bonus_searches: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT points FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row or row[0] < points:
            return False
        await db.execute(
            "UPDATE users SET points=points-?, bonus_searches=bonus_searches+? WHERE user_id=?",
            (points, bonus_searches, user_id)
        )
        await db.commit()
        return True


# ─── Price alert helpers ───────────────────────────────────────────────────────

async def add_price_alert(user_id: int, product_name: str, target_price: float,
                           current_price: float, store: str, currency: str = "EGP",
                           product_url: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO price_alerts
               (user_id, product_name, product_url, target_price, current_price, currency, store)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id, product_name, product_url, target_price, current_price, currency, store)
        )
        await db.commit()


async def get_active_alerts() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM price_alerts WHERE active=1")
        return [dict(r) for r in await cur.fetchall()]


async def deactivate_alert(alert_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE price_alerts SET active=0 WHERE id=?", (alert_id,))
        await db.commit()


async def get_user_alerts(user_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM price_alerts WHERE user_id=? AND active=1", (user_id,)
        )
        return [dict(r) for r in await cur.fetchall()]


# ─── Referral helpers ─────────────────────────────────────────────────────────

async def process_referral(new_user_id: int, ref_code: str) -> int:
    """Returns points awarded to referrer, 0 if invalid."""
    from config.settings import settings
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE referral_code=?", (ref_code,))
        referrer = await cur.fetchone()
        if not referrer:
            return 0
        referrer = dict(referrer)
        if referrer["user_id"] == new_user_id:
            return 0
        # Check not already referred
        cur2 = await db.execute(
            "SELECT id FROM referral_rewards WHERE referred_id=?", (new_user_id,)
        )
        if await cur2.fetchone():
            return 0

        count = referrer["referral_count"] + 1
        # Milestone bonuses
        if count >= 50:
            pts = settings.POINTS_50_FRIENDS
        elif count >= 10:
            pts = settings.POINTS_10_FRIENDS
        elif count >= 5:
            pts = settings.POINTS_5_FRIENDS
        else:
            pts = settings.REFERRAL_POINTS_PER_FRIEND

        await db.execute(
            "UPDATE users SET referral_count=referral_count+1, points=points+?, referred_by=? WHERE user_id=?",
            (pts, referrer["user_id"], new_user_id)
        )
        await db.execute(
            "UPDATE users SET points=points+? WHERE user_id=?",
            (pts, referrer["user_id"])
        )
        await db.execute(
            "INSERT INTO referral_rewards (referrer_id, referred_id, points_earned) VALUES (?,?,?)",
            (referrer["user_id"], new_user_id, pts)
        )
        await db.commit()
        return pts
