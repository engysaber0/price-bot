"""
Product search engine - with better timeout handling and fallbacks.
"""
import asyncio
import logging
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
}

TIMEOUT = 10  # seconds


async def search_google_shopping(query: str, country: str = "us") -> list:
    if not settings.SERPAPI_KEY:
        return []
    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": "us",
        "hl": "en",
        "api_key": settings.SERPAPI_KEY,
        "num": 10,
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get("https://serpapi.com/search", params=params)
            data = r.json()

        if "error" in data:
            logger.warning(f"SerpAPI returned an error: {data['error']}")
            return []

        results = []
        for item in data.get("shopping_results", []):
            store = _detect_store(item.get("source", ""))

            price = item.get("extracted_price")
            if price is None:
                price = _parse_price(item.get("price", "0"))

            if not price or price <= 0:
                continue

            currency = _detect_currency_from_price_string(item.get("price", ""))

            results.append({
                "name": item.get("title", ""),
                "price": float(price),
                "rating": float(item.get("rating", 0) or 0),
                "reviews": int(item.get("reviews", 0) or 0),
                "url": item.get("link", item.get("product_link", "#")),
                "image_url": item.get("thumbnail", ""),
                "store": store,
                "currency": currency,
            })
        return results
    except Exception as e:
        logger.warning(f"SerpAPI error: {e}")
        return []


def _detect_currency_from_price_string(price_str: str) -> str:
    s = price_str.upper()
    if "EGP" in s or "E£" in s or "ج.م" in price_str:
        return "EGP"
    if "$" in price_str or "USD" in s:
        return "USD"
    if "€" in price_str or "EUR" in s:
        return "EUR"
    if "£" in price_str or "GBP" in s:
        return "GBP"
    if "SAR" in s or "ر.س" in price_str:
        return "SAR"
    if "AED" in s or "د.إ" in price_str:
        return "AED"
    return "USD"


async def search_noon(query: str) -> list:
    url = f"https://www.noon.com/egypt-en/search/?q={query.replace(' ', '+')}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            r = await client.get(url)

        if r.status_code != 200:
            logger.warning(f"Noon blocked request (status {r.status_code}) for query: {query}")
            return [_search_link_fallback(query, "noon", url, "EGP")]

        from bs4 import BeautifulSoup
        import json
        soup = BeautifulSoup(r.text, "html.parser")
        results = []

        for tag in soup.find_all("script", type="application/ld+json"):
            try:
                d = json.loads(tag.string or "{}")
                if d.get("@type") == "Product":
                    offer = d.get("offers", {})
                    price = float(offer.get("price", 0) or 0)
                    if price >= 10:
                        results.append({
                            "name": d.get("name", query),
                            "price": price,
                            "rating": float(d.get("aggregateRating", {}).get("ratingValue", 0) or 0),
                            "reviews": int(d.get("aggregateRating", {}).get("reviewCount", 0) or 0),
                            "url": url,
                            "image_url": "",
                            "store": "noon",
                            "currency": "EGP",
                        })
            except Exception:
                continue

        if not results:
            logger.warning(f"Noon: no structured product data found for query: {query}")
            return [_search_link_fallback(query, "noon", url, "EGP")]
        return results
    except Exception as e:
        logger.warning(f"Noon error: {e}")
        return [_search_link_fallback(query, "noon", url, "EGP")]


async def search_amazon_eg(query: str) -> list:
    try:
        url = f"https://www.amazon.eg/-/en/s?k={query.replace(' ', '+')}"
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            r = await client.get(url)

        if r.status_code != 200:
            logger.warning(f"Amazon EG blocked request (status {r.status_code}) for query: {query}")
            return [_search_link_fallback(query, "amazon", url, "EGP")]

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        results = []

        search_results = soup.select('[data-component-type="s-search-result"]')
        if not search_results:
            logger.warning(f"Amazon EG returned unexpected page structure for query: {query}")
            return [_search_link_fallback(query, "amazon", url, "EGP")]

        for item in search_results[:4]:
            try:
                name_el = item.select_one("h2 span")
                price_whole = item.select_one(".a-price-whole")
                price_frac = item.select_one(".a-price-fraction")
                rating_el = item.select_one(".a-icon-alt")
                reviews_el = item.select_one(".a-size-base.s-underline-text")
                link_el = item.select_one("h2 a")

                if not (name_el and price_whole):
                    continue

                name = name_el.text.strip()
                whole = price_whole.text.strip().replace(",", "").replace(".", "")
                frac = price_frac.text.strip() if price_frac else "0"
                try:
                    price = float(f"{whole}.{frac}")
                except Exception:
                    continue

                rating_text = rating_el.text if rating_el else "0"
                try:
                    rating = float(rating_text.split()[0])
                except Exception:
                    rating = 0

                reviews_text = reviews_el.text.replace(",", "").strip() if reviews_el else "0"
                try:
                    reviews = int(reviews_text)
                except Exception:
                    reviews = 0

                link = ("https://www.amazon.eg" + link_el["href"]) if link_el else url

                if name and price >= 10:
                    results.append({
                        "name": name,
                        "price": price,
                        "rating": rating,
                        "reviews": reviews,
                        "url": link,
                        "image_url": "",
                        "store": "amazon",
                        "currency": "EGP",
                    })
            except Exception:
                continue

        if not results:
            return [_search_link_fallback(query, "amazon", url, "EGP")]
        return results
    except Exception as e:
        logger.warning(f"Amazon EG error: {e}")
        return [_search_link_fallback(query, "amazon",
                f"https://www.amazon.eg/-/en/s?k={query.replace(' ', '+')}", "EGP")]


async def search_aliexpress(query: str) -> list:
    url = f"https://www.aliexpress.com/wholesale?SearchText={query.replace(' ', '+')}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            r = await client.get(url)

        from bs4 import BeautifulSoup
        import re
        soup = BeautifulSoup(r.text, "html.parser")
        results = []

        for item in soup.select(".search-item-card-wrapper-gallery")[:5]:
            try:
                price_el = item.select_one(".price--current--I3Zeidd")
                name_el = item.select_one(".multi--titleText--nXeOvyr")
                link_el = item.select_one("a")

                if not (price_el and name_el):
                    continue

                price_text = re.sub(r"[^\d.]", "", price_el.text.strip())
                price = float(price_text) if price_text else 0

                if price <= 0:
                    continue

                results.append({
                    "name": name_el.text.strip(),
                    "price": price,
                    "rating": 0,
                    "reviews": 0,
                    "url": "https:" + link_el["href"] if link_el else url,
                    "image_url": "",
                    "store": "aliexpress",
                    "currency": "USD",
                })
            except Exception:
                continue

        if results:
            return results
    except Exception as e:
        logger.warning(f"AliExpress error: {e}")

    return [_search_link_fallback(query, "aliexpress", url, "USD")]


def _search_link_fallback(query: str, store: str, url: str, currency: str) -> dict:
    store_names_ar = {"noon": "نون مصر", "amazon": "أمازون مصر", "aliexpress": "علي إكسبريس"}
    return {
        "name": f"{query} - {store_names_ar.get(store, store)}",
        "price": 0,
        "rating": 0,
        "reviews": 0,
        "url": url,
        "image_url": "",
        "store": store,
        "currency": currency,
        "is_search_link": True,
    }


async def multi_store_search(query: str) -> list:
    tasks = [
        asyncio.wait_for(search_google_shopping(query), timeout=12),
        asyncio.wait_for(search_noon(query), timeout=12),
        asyncio.wait_for(search_amazon_eg(query), timeout=12),
        asyncio.wait_for(search_aliexpress(query), timeout=5),
    ]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)
    merged = []
    for res in all_results:
        if isinstance(res, list):
            merged.extend(res)
        elif isinstance(res, Exception):
            logger.warning(f"Search task failed: {res}")

    merged = _deduplicate(merged)
    merged = _filter_relevant(merged, query)

    stores_with_real_price = {r["store"] for r in merged if r.get("price", 0) > 0}
    merged = [
        r for r in merged
        if r.get("price", 0) > 0 or r["store"] not in stores_with_real_price
    ]

    real = [r for r in merged if r.get("price", 0) > 0]
    links = [r for r in merged if r.get("price", 0) == 0]
    real.sort(key=lambda x: x.get("price", 9999999))
    return real + links


ACCESSORY_KEYWORDS = [
    "case", "cover", "screen protector", "charger", "cable", "adapter",
    "strap", "stand", "holder", "skin", "sticker", "tempered glass",
    "غطاء", "جراب", "كفر", "شاحن", "كابل", "حامي شاشة", "سلك",
]


def _filter_relevant(results: list, query: str) -> list:
    query_words = set(query.lower().split())
    filtered = []
    for r in results:
        if r.get("price", 0) <= 0:
            filtered.append(r)
            continue

        name_lower = r.get("name", "").lower()
        is_accessory = any(kw in name_lower for kw in ACCESSORY_KEYWORDS)

        if is_accessory:
            logger.info(f"Filtered out likely accessory: {r.get('name', '')[:50]}")
            continue

        filtered.append(r)

    return filtered if filtered else results


def _deduplicate(results: list) -> list:
    seen = set()
    unique = []
    for r in results:
        key = (r.get("store", ""), r.get("name", "")[:30].lower())
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _detect_store(source: str) -> str:
    src = source.lower()
    if "noon" in src:
        return "noon"
    if "amazon" in src:
        return "amazon"
    if "aliexpress" in src:
        return "aliexpress"
    if "jumia" in src:
        return "jumia"
    return source or "other"


def _parse_price(text: str) -> float:
    import re
    nums = re.findall(r"[\d]+", str(text).replace(",", ""))
    for n in nums:
        try:
            v = float(n)
            if v > 0:
                return v
        except Exception:
            pass
    return 0.0