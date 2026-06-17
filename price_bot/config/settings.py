"""
Configuration settings loaded from environment variables / .env file
"""
import os
from dataclasses import dataclass, field
from typing import List, Tuple
from dotenv import load_dotenv

load_dotenv()


def _parse_coupons(raw: str) -> List[Tuple[str, str, str]]:
    """Parse STORE:CODE:DISCOUNT,... into list of tuples"""
    result = []
    for entry in raw.split(","):
        parts = entry.strip().split(":")
        if len(parts) == 3:
            result.append((parts[0].upper(), parts[1], parts[2]))
    return result


@dataclass
class Settings:
    # Core
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///bot.db"))

    # Affiliate IDs
    NOON_AFFILIATE_ID: str = field(default_factory=lambda: os.getenv("NOON_AFFILIATE_ID", ""))
    AMAZON_AFFILIATE_TAG: str = field(default_factory=lambda: os.getenv("AMAZON_AFFILIATE_TAG", ""))
    ALIEXPRESS_AFFILIATE_KEY: str = field(default_factory=lambda: os.getenv("ALIEXPRESS_AFFILIATE_KEY", ""))

    # Optional APIs
    STRIPE_SECRET_KEY: str = field(default_factory=lambda: os.getenv("STRIPE_SECRET_KEY", ""))
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))
    GOOGLE_VISION_API_KEY: str = field(default_factory=lambda: os.getenv("GOOGLE_VISION_API_KEY", ""))
    SERPAPI_KEY: str = field(default_factory=lambda: os.getenv("SERPAPI_KEY", ""))  # for Google Shopping

    # Coupons parsed from env
    COUPONS: List[Tuple[str, str, str]] = field(
        default_factory=lambda: _parse_coupons(os.getenv("COUPONS", "NOON:SAVE10:10%,AMAZON:PRIME5:5%"))
    )

    # Subscription limits (configurable via .env, with sensible defaults)
    FREE_SEARCHES_PER_DAY: int = field(
        default_factory=lambda: int(os.getenv("FREE_SEARCHES_PER_DAY", "3"))
    )
    BASIC_SEARCHES_PER_DAY: int = field(
        default_factory=lambda: int(os.getenv("BASIC_SEARCHES_PER_DAY", "30"))
    )
    PRO_SEARCHES_PER_DAY: int = field(
        default_factory=lambda: int(os.getenv("PRO_SEARCHES_PER_DAY", "999"))
    )

    # Subscription prices (USD)
    BASIC_PRICE_USD: float = field(
        default_factory=lambda: float(os.getenv("BASIC_PRICE_USD", "1.0"))
    )
    PRO_PRICE_USD: float = field(
        default_factory=lambda: float(os.getenv("PRO_PRICE_USD", "3.0"))
    )

    # Referral points
    REFERRAL_POINTS_PER_FRIEND: int = 3
    POINTS_5_FRIENDS: int = 10       # bonus at 5 friends
    POINTS_10_FRIENDS: int = 50      # bonus at 10 friends
    POINTS_50_FRIENDS: int = 100     # bonus at 50 friends

    # Points redemption
    POINTS_50_GIVES_SEARCHES: int = 10
    POINTS_100_GIVES_SEARCHES: int = 20

    # Admin telegram user IDs (comma-separated in env)
    ADMIN_IDS: List[int] = field(
        default_factory=lambda: [
            int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
        ]
    )


settings = Settings()