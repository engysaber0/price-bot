"""
Affiliate link builder for Noon, Amazon, AliExpress, etc.
"""
from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
from config.settings import settings


def build_noon_affiliate(product_url: str) -> str:
    if not settings.NOON_AFFILIATE_ID:
        return product_url
    sep = "&" if "?" in product_url else "?"
    return f"{product_url}{sep}affiliate_id={settings.NOON_AFFILIATE_ID}"


def build_amazon_affiliate(product_url: str) -> str:
    if not settings.AMAZON_AFFILIATE_TAG:
        return product_url
    parsed = urlparse(product_url)
    params = parse_qs(parsed.query)
    params["tag"] = [settings.AMAZON_AFFILIATE_TAG]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))


def build_aliexpress_affiliate(product_url: str) -> str:
    # AliExpress deep links need their portal, simplified version:
    if not settings.ALIEXPRESS_AFFILIATE_KEY:
        return product_url
    sep = "&" if "?" in product_url else "?"
    return f"{product_url}{sep}aff_key={settings.ALIEXPRESS_AFFILIATE_KEY}"


AFFILIATE_BUILDERS = {
    "noon": build_noon_affiliate,
    "amazon": build_amazon_affiliate,
    "aliexpress": build_aliexpress_affiliate,
}


def apply_affiliate(url: str, store: str) -> str:
    builder = AFFILIATE_BUILDERS.get(store.lower())
    return builder(url) if builder else url


def get_coupons_for_store(store: str) -> list[tuple[str, str]]:
    """Returns list of (code, discount) for given store."""
    store_upper = store.upper()
    return [
        (code, discount)
        for s, code, discount in settings.COUPONS
        if s == store_upper
    ]
