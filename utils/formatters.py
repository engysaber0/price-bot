"""
Message formatting helpers.
"""
from utils.affiliate import apply_affiliate, get_coupons_for_store


STORE_FLAGS = {
    "noon": "🟡",
    "amazon": "📦",
    "aliexpress": "🛍️",
    "jumia": "🟠",
    "other": "🏪",
}


def flag(store: str) -> str:
    return STORE_FLAGS.get(store.lower(), "🏪")


def format_price_results(results: list[dict], currency: str = "EGP") -> str:
    """
    results: list of {store, name, price, rating, reviews, url, image_url, display_currency?}
    `currency` is the target/expected currency (used for the summary line).
    Each item may carry its own 'display_currency' if conversion fell back
    to the original currency for that store (e.g. exchange API was unreachable).
    Returns formatted message text.
    """
    if not results:
        return "❌ لم يتم العثور على نتائج. جرّب صياغة أخرى."

    priced = [r for r in results if r.get("price", 0) > 0]
    link_only = [r for r in results if r.get("price", 0) == 0]

    if not priced:
        # No real prices found anywhere — just give search links
        lines = ["🔎 لم أجد أسعاراً مباشرة، لكن هذه روابط بحث جاهزة:\n"]
        for r in link_only:
            aff_url = apply_affiliate(r.get("url", "#"), r.get("store", "other"))
            lines.append(f"{flag(r['store'])} [{r['store'].upper()}]({aff_url})")
        return "\n".join(lines)

    sorted_results = sorted(priced, key=lambda x: x.get("price", 9999999))
    best = sorted_results[0]
    worst = sorted_results[-1]
    same_currency = len({r.get("display_currency", currency) for r in sorted_results}) == 1
    saving = (worst["price"] - best["price"]) if (len(sorted_results) > 1 and same_currency) else 0

    lines = ["━━━━━━━━━━━━━━━━━━━━━━", "📊 *مقارنة الأسعار*", "━━━━━━━━━━━━━━━━━━━━━━\n"]

    for i, r in enumerate(sorted_results):
        aff_url = apply_affiliate(r.get("url", "#"), r.get("store", "other"))
        coupons = get_coupons_for_store(r.get("store", ""))
        coupon_text = ""
        if coupons:
            codes = " | ".join(f"`{c}` ({d})" for c, d in coupons)
            coupon_text = f"\n   🎟 كوبون: {codes}"

        crown = "👑 " if i == 0 else ""
        stars = _rating_stars(r.get("rating", 0))
        reviews = f"({r.get('reviews', 0):,} تقييم)" if r.get("reviews") else ""
        item_currency = r.get("display_currency", currency)
        converted_note = ""
        if r.get("original_currency") and r["original_currency"] != item_currency:
            converted_note = f" _(تحويل من {r['original_price']:,.0f} {r['original_currency']})_"

        product_name = r.get("name", "").strip()
        name_line = f"   📦 _{product_name[:60]}_\n" if product_name else ""

        lines.append(
            f"{crown}{flag(r['store'])} *{r['store'].upper()}*\n"
            f"{name_line}"
            f"   💰 {r['price']:,.0f} {item_currency}{converted_note}\n"
            f"   ⭐ {stars} {reviews}\n"
            f"   🔗 [شراء هنا]({aff_url}){coupon_text}\n"
        )

    best_currency = best.get("display_currency", currency)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"✅ *أفضل صفقة:* {flag(best['store'])} {best['store'].upper()}")
    lines.append(f"💰 *السعر:* {best['price']:,.0f} {best_currency}")
    if saving > 0:
        lines.append(f"💸 *وفّرت:* {saving:,.0f} {best_currency} مقارنةً بأغلى سعر!")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    if link_only:
        lines.append("\n🔎 *روابط بحث إضافية:*")
        for r in link_only:
            aff_url = apply_affiliate(r.get("url", "#"), r.get("store", "other"))
            lines.append(f"{flag(r['store'])} [{r['store'].upper()}]({aff_url})")

    return "\n".join(lines)


def format_product_card(r: dict, currency: str = "EGP", rank: int = 1) -> str:
    aff_url = apply_affiliate(r.get("url", "#"), r.get("store", "other"))
    stars = _rating_stars(r.get("rating", 0))
    coupons = get_coupons_for_store(r.get("store", ""))
    coupon_text = ""
    if coupons:
        codes = " | ".join(f"`{c}` ({d})" for c, d in coupons)
        coupon_text = f"\n🎟 *كوبون خصم:* {codes}"

    pros = "\n".join(f"  ✅ {p}" for p in r.get("pros", []))
    cons = "\n".join(f"  ❌ {c}" for c in r.get("cons", []))
    pros_cons = ""
    if pros:
        pros_cons += f"\n*المميزات:*\n{pros}"
    if cons:
        pros_cons += f"\n*العيوب:*\n{cons}"

    item_currency = r.get("display_currency", currency)

    return (
        f"{'🥇' if rank==1 else '🥈' if rank==2 else '🥉'} *{r.get('name','منتج')}*\n"
        f"{flag(r['store'])} {r['store'].upper()} | 💰 {r['price']:,.0f} {item_currency}\n"
        f"⭐ {stars} ({r.get('reviews',0):,} تقييم)\n"
        f"🔗 [رابط الشراء]({aff_url}){coupon_text}{pros_cons}"
    )


def _rating_stars(rating: float) -> str:
    full = int(rating)
    half = 1 if (rating - full) >= 0.5 else 0
    empty = 5 - full - half
    return "★" * full + "½" * half + "☆" * empty + f" {rating:.1f}"


def format_comparison(product_a: dict, product_b: dict) -> str:
    specs_a = product_a.get("specs", {})
    specs_b = product_b.get("specs", {})
    all_keys = set(list(specs_a.keys()) + list(specs_b.keys()))

    rows = [
        f"⚔️ *مقارنة: {product_a['name']} vs {product_b['name']}*\n",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{'المواصفة':<20} | {product_a['name'][:12]:<12} | {product_b['name'][:12]}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for k in sorted(all_keys):
        va = specs_a.get(k, "—")
        vb = specs_b.get(k, "—")
        rows.append(f"{'• ' + k:<20} | {str(va):<12} | {vb}")

    rows.append("━━━━━━━━━━━━━━━━━━━━━━")
    # Price comparison
    pa, pb = product_a.get("price", 0), product_b.get("price", 0)
    winner = product_a["name"] if pa <= pb else product_b["name"]
    rows.append(f"💰 أرخص: *{winner}*")
    ra, rb = product_a.get("rating", 0), product_b.get("rating", 0)
    better_rated = product_a["name"] if ra >= rb else product_b["name"]
    rows.append(f"⭐ أعلى تقييم: *{better_rated}*")

    return "\n".join(rows)