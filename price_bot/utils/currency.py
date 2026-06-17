"""
Currency detection & conversion based on the user's Telegram language_code
(Telegram does not expose precise country, so we map language_code -> a
likely country/currency. This is a best-effort heuristic, not exact geo-IP).

Exchange rates are fetched from a free API and cached for a few hours,
since hardcoding rates would go stale and mislead users on actual savings.
"""
import time
import logging
import httpx

logger = logging.getLogger(__name__)

# language_code -> (currency_code, country_name_ar)
LANG_TO_CURRENCY = {
    "ar": ("EGP", "مصر"),      # default Arabic -> Egypt (bot's primary market)
    "en": ("USD", "أمريكا"),
    "fr": ("EUR", "فرنسا"),
    "de": ("EUR", "ألمانيا"),
    "es": ("EUR", "إسبانيا"),
    "ru": ("RUB", "روسيا"),
    "tr": ("TRY", "تركيا"),
}

# More specific overrides if Telegram gives a region-tagged code, e.g. "ar-SA"
REGION_OVERRIDES = {
    "ar-eg": ("EGP", "مصر"),
    "ar-sa": ("SAR", "السعودية"),
    "ar-ae": ("AED", "الإمارات"),
    "ar-kw": ("KWD", "الكويت"),
    "ar-qa": ("QAR", "قطر"),
    "ar-jo": ("JOD", "الأردن"),
    "ar-ma": ("MAD", "المغرب"),
    "en-us": ("USD", "أمريكا"),
    "en-gb": ("GBP", "بريطانيا"),
}

DEFAULT_CURRENCY = ("EGP", "مصر")

_rate_cache: dict = {}
_cache_time: float = 0
CACHE_TTL = 6 * 3600  # 6 hours


def detect_currency_from_user(telegram_user) -> tuple[str, str]:
    """
    telegram_user: telegram.User object (has .language_code)
    Returns (currency_code, country_name_ar)
    """
    code = (getattr(telegram_user, "language_code", None) or "").lower()
    if not code:
        return DEFAULT_CURRENCY

    if code in REGION_OVERRIDES:
        return REGION_OVERRIDES[code]

    base = code.split("-")[0]
    return LANG_TO_CURRENCY.get(base, DEFAULT_CURRENCY)


async def _refresh_rates():
    """Fetch latest rates with EGP as base, cache them."""
    global _rate_cache, _cache_time
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://api.exchangerate-api.com/v4/latest/EGP")
            data = r.json()
        rates = data.get("rates", {})
        if rates:
            _rate_cache = rates
            _cache_time = time.time()
    except Exception as e:
        logger.warning(f"Exchange rate fetch failed: {e}")


async def get_rate_egp_to(target_currency: str) -> float | None:
    """Returns how many units of target_currency equal 1 EGP."""
    global _cache_time
    if target_currency.upper() == "EGP":
        return 1.0

    if not _rate_cache or (time.time() - _cache_time) > CACHE_TTL:
        await _refresh_rates()

    return _rate_cache.get(target_currency.upper())


async def convert_price(amount: float, from_currency: str, to_currency: str) -> float | None:
    """Convert an amount between two currencies via EGP as pivot."""
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == to_currency:
        return amount

    if not _rate_cache or (time.time() - _cache_time) > CACHE_TTL:
        await _refresh_rates()

    if not _rate_cache:
        return None  # API unreachable, caller should fall back to original currency

    rate_from = 1.0 if from_currency == "EGP" else _rate_cache.get(from_currency)
    rate_to = 1.0 if to_currency == "EGP" else _rate_cache.get(to_currency)

    if rate_from is None or rate_to is None:
        return None

    amount_in_egp = amount / rate_from
    return amount_in_egp * rate_to


async def convert_results_to_currency(results: list[dict], target_currency: str) -> list[dict]:
    """
    Takes scraper results (each with its own 'price' + 'currency'),
    converts every price to target_currency, and tags the result with
    'display_currency'. Original price/currency are kept under
    'original_price'/'original_currency' for transparency.
    """
    converted = []
    for r in results:
        item = dict(r)
        src_currency = item.get("currency", "EGP")
        price = item.get("price", 0)

        if price <= 0:
            item["display_currency"] = target_currency
            converted.append(item)
            continue

        new_price = await convert_price(price, src_currency, target_currency)
        if new_price is None:
            # Conversion unavailable -> keep original currency, mark it clearly
            item["display_currency"] = src_currency
        else:
            item["original_price"] = price
            item["original_currency"] = src_currency
            item["price"] = round(new_price, 2)
            item["display_currency"] = target_currency

        converted.append(item)
    return converted
