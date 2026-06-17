"""
Handles all text messages — routes based on user conversation state.
"""
import re
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import (
    get_or_create_user, get_user_state, set_user_state,
    can_search, increment_search_count, get_user, get_user_currency
)
from utils.formatters import format_price_results, format_product_card
from scrapers.search_engine import multi_store_search


async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()

    await get_or_create_user(user.id, user.username or "", user.full_name or "",
                              language_code=user.language_code)
    state = await get_user_state(user.id)

    if state == "compare_two":
        await handle_compare_two(update, context, text)
        return

    if state == "smart_agent":
        await handle_smart_agent(update, context, text)
        return

    if state == "smart_gift":
        from handlers.smart_gift import handle_smart_gift_text
        await handle_smart_gift_text(update, context, text)
        return

    if state == "fake_detect":
        await handle_fake_detect_text(update, context, text)
        return

    await handle_price_search(update, context, text)


async def handle_price_search(update, context, query: str):
    user_id = update.effective_user.id

    allowed, reason = await can_search(user_id)
    if not allowed:
        await update.message.reply_text(
            f"🔒 {reason}\n\n"
            "ترقّ للخطة الأساسية بـ 1$/شهر فقط! /subscribe",
            parse_mode="Markdown"
        )
        return

    msg = await update.message.reply_text("⏳ جاري البحث في المتاجر...")

    results = await multi_store_search(query)
    await increment_search_count(user_id)

    if not results:
        await msg.edit_text(
            "❌ لم أجد نتائج. جرب صياغة مختلفة أو اكتب اسم المنتج بالإنجليزية."
        )
        return

    # Default to EGP for Arabic/Egyptian users
    # Only use DB currency if it's not USD (USD is usually wrong for Arab users)
    db_currency = await get_user_currency(user_id)
    user_currency = db_currency if (db_currency and db_currency != "USD") else "EGP"

    # Override with currency mentioned in the query
    currency_map = {
        "جنيه": "EGP", "pounds": "EGP", "egp": "EGP",
        "دولار": "USD", "dollar": "USD", "usd": "USD",
        "ريال": "SAR", "sar": "SAR",
        "درهم": "AED", "aed": "AED",
    }
    query_lower = query.lower()
    for keyword, code in currency_map.items():
        if keyword in query_lower:
            user_currency = code
            break

    # Extract budget if mentioned
    budget_match = re.search(
        r"(\d[\d,]*)\s*(جنيه|دولار|ريال|درهم|egp|usd|sar|aed)"
        r"|(بـ|بسعر|أقل من|تحت)\s*(\d[\d,]*)",
        query_lower
    )
    budget_limit = None
    if budget_match:
        num = budget_match.group(1) or budget_match.group(4)
        if num:
            budget_limit = float(num.replace(",", ""))

    # Force fallback rates if cache is empty
    import utils.currency as _cur
    if not _cur._rate_cache:
        _cur._rate_cache = _cur.FALLBACK_RATES
        _cur._cache_time = time.time()

    # Convert first, then filter
    from utils.currency import convert_results_to_currency
    results = await convert_results_to_currency(results, user_currency)

    if budget_limit:
        filtered = [r for r in results if 0 < r.get("price", 0) <= budget_limit]
        if filtered:
            results = filtered

    display_currency = results[0].get("display_currency", user_currency) if results else user_currency
    text = format_price_results(results, currency=display_currency)

    best = results[0]

    pending_alerts = context.user_data.setdefault("pending_alerts", {})
    alert_idx = str(len(pending_alerts))
    pending_alerts[alert_idx] = {
        "store": best["store"],
        "price": best["price"],
        "query": query,
    }

    alert_btn = InlineKeyboardMarkup([
        [InlineKeyboardButton(
            f"🔔 نبّهني لما يوصل {int(best['price'] * 0.9):,}",
            callback_data=f"alert:set:{alert_idx}"
        )],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")]
    ])

    await msg.edit_text(text, parse_mode="Markdown", reply_markup=alert_btn,
                        disable_web_page_preview=True)


async def handle_compare_two(update, context, text: str):
    user_id = update.effective_user.id

    if "vs" not in text.lower():
        await update.message.reply_text(
            "⚔️ يرجى كتابة المنتجَين مفصولَين بـ `vs`\nمثال: `iPhone 15 vs Galaxy S24`",
            parse_mode="Markdown"
        )
        return

    allowed, reason = await can_search(user_id)
    if not allowed:
        await update.message.reply_text(f"🔒 {reason}")
        return

    parts = text.lower().split("vs", 1)
    q1, q2 = parts[0].strip(), parts[1].strip()

    msg = await update.message.reply_text("⏳ جاري المقارنة...")

    import asyncio
    from scrapers.search_engine import multi_store_search
    r1, r2 = await asyncio.gather(multi_store_search(q1), multi_store_search(q2))

    await increment_search_count(user_id)
    await set_user_state(user_id, "idle")

    if not r1 or not r2:
        await msg.edit_text("❌ لم أجد أحد المنتجَين. تأكد من الأسماء.")
        return

    p1, p2 = r1[0], r2[0]
    p1["name"] = q1.title()
    p2["name"] = q2.title()

    from utils.formatters import format_comparison
    comp_text = format_comparison(p1, p2)

    from utils.affiliate import apply_affiliate
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🛒 {q1.title()[:15]}", url=apply_affiliate(p1["url"], p1["store"])),
            InlineKeyboardButton(f"🛒 {q2.title()[:15]}", url=apply_affiliate(p2["url"], p2["store"])),
        ],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")]
    ])
    await msg.edit_text(comp_text, parse_mode="Markdown", reply_markup=kb,
                        disable_web_page_preview=True)


async def handle_smart_agent(update, context, text: str):
    user_id = update.effective_user.id

    allowed, reason = await can_search(user_id)
    if not allowed:
        await update.message.reply_text(f"🔒 {reason}")
        return

    msg = await update.message.reply_text("🤖 الوكيل الذكي يحلل طلبك...")

    db_currency = await get_user_currency(user_id)
    user_currency = db_currency if (db_currency and db_currency != "USD") else "EGP"

    budget_match = re.search(r"(\d[\d,\.]*)\s*(دولار|جنيه|ريال|\$|USD|EGP|SAR)?", text, re.IGNORECASE)
    budget = float(budget_match.group(1).replace(",", "")) if budget_match else None
    budget_currency = (budget_match.group(2) or user_currency) if budget_match else user_currency
    budget_currency = {"دولار": "USD", "جنيه": "EGP", "ريال": "SAR", "$": "USD"}.get(
        budget_currency, budget_currency
    ).upper()

    results = await multi_store_search(text)
    await increment_search_count(user_id)
    await set_user_state(user_id, "idle")

    if not results:
        await msg.edit_text("❌ لم أجد منتجات مناسبة. جرب وصفاً مختلفاً.")
        return

    # Force fallback rates if cache is empty
    import utils.currency as _cur
    if not _cur._rate_cache:
        _cur._rate_cache = _cur.FALLBACK_RATES
        _cur._cache_time = time.time()

    from utils.currency import convert_results_to_currency
    results = await convert_results_to_currency(results, budget_currency)

    if budget:
        filtered = [r for r in results if r.get("price", 0) > 0 and r["price"] <= budget]
        if filtered:
            results = filtered

    priced_results = [r for r in results if r.get("price", 0) > 0]
    if not priced_results:
        await msg.edit_text(
            "❌ لم أجد منتجات بسعر متاح ضمن ميزانيتك. جرب ميزانية أعلى أو وصفاً مختلفاً."
        )
        return

    priced_results.sort(key=lambda r: (r.get("rating", 0) / max(r.get("price", 1), 1)), reverse=True)

    best = priced_results[0]
    alternatives = priced_results[1:3]

    from utils.formatters import format_product_card
    from utils.affiliate import apply_affiliate

    lines = [
        "🤖 *توصية الوكيل الذكي*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "🏆 *أفضل اختيار لك:*",
        format_product_card(best, rank=1),
        "",
        f"💡 *سبب الاختيار:* أعلى قيمة مقابل السعر"
        + (f" وضمن ميزانيتك ({budget:,.0f} {budget_currency})" if budget else ""),
    ]

    if alternatives:
        lines.append("\n📋 *بدائل:*")
        for i, alt in enumerate(alternatives, 2):
            lines.append(format_product_card(alt, rank=i))

    lines += ["", "━━━━━━━━━━━━━━━━━━━━━━"]

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 اشتري الآن", url=apply_affiliate(best["url"], best["store"]))],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")]
    ])

    await msg.edit_text("\n".join(lines), parse_mode="Markdown",
                        reply_markup=kb, disable_web_page_preview=True)


async def handle_fake_detect_text(update, context, text: str):
    user_id = update.effective_user.id
    await set_user_state(user_id, "idle")

    msg = await update.message.reply_text("🔍 جاري تحليل المنتج...")

    results = await multi_store_search(text)

    if not results:
        await msg.edit_text("❌ لم أجد المنتج. تأكد من الاسم أو الرابط.")
        return

    from scrapers.fake_detector import analyze_product, format_fake_report
    product = results[0]
    analysis = analyze_product(product)
    report = format_fake_report(product, analysis)

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")]
    ])
    await msg.edit_text(report, parse_mode="Markdown", reply_markup=kb)


def _detect_currency(results: list[dict]) -> str:
    currencies = [r.get("currency", "EGP") for r in results]
    return max(set(currencies), key=currencies.count) if currencies else "EGP"
