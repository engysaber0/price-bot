"""
Handles all text messages — routes based on user conversation state.
"""
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

    # Default: price comparison search
    await handle_price_search(update, context, text)


async def handle_price_search(update, context, query: str):
    user_id = update.effective_user.id

    # Check limits
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

    # Convert all prices into the user's detected currency for a fair comparison
    user_currency = await get_user_currency(user_id)
    from utils.currency import convert_results_to_currency
    results = await convert_results_to_currency(results, user_currency)

    display_currency = results[0].get("display_currency", user_currency) if results else user_currency
    text = format_price_results(results, currency=display_currency)

    # Build alert button for best result
    best = results[0]

    # callback_data has a hard 64-byte limit in Telegram, and Arabic text
    # easily exceeds that in UTF-8 (multiple bytes per character). Store the
    # actual alert details in user_data and reference them by a short index
    # instead of cramming the product name into callback_data.
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

    user_currency = await get_user_currency(user_id)

    # Extract budget + intent
    import re
    budget_match = re.search(r"(\d[\d,\.]*)\s*(دولار|جنيه|ريال|\$|USD|EGP|SAR)?", text, re.IGNORECASE)
    budget = float(budget_match.group(1).replace(",", "")) if budget_match else None
    # If user didn't specify a currency word, assume their detected currency
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

    # Convert every result into the budget's currency so comparison is apples-to-apples
    from utils.currency import convert_results_to_currency
    results = await convert_results_to_currency(results, budget_currency)

    # Filter by budget if detected (now safe since everything's in the same currency)
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

    # Sort by value score: rating / price
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