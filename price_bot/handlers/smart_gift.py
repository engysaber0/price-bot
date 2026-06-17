"""
Smart Gift Section (Section 8) - separate from Smart Purchase Agent (Section 6).
User describes a person (age, interests) -> bot suggests gift products.
"""
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import set_user_state, can_search, increment_search_count
from scrapers.search_engine import multi_store_search
from utils.formatters import format_product_card
from utils.affiliate import apply_affiliate

GIFT_PROMPT = (
    "🎁 *القسم الذكي — اقتراح الهدايا*\n\n"
    "أخبرني عن الشخص (العمر + اهتماماته) وسأقترح له أفضل هدية!\n\n"
    "مثال:\n"
    "• _هدية لشخص عمره 25 سنة ويحب الألعاب_\n"
    "• _هدية لبنت عمرها 10 سنين تحب الرسم_\n"
    "• _هدية لأمي بمناسبة عيد ميلادها وتحب الطبخ_"
)

# Maps interest keywords -> search terms to query the stores with
INTEREST_MAP = {
    "العاب": "gaming gift", "ألعاب": "gaming gift", "gaming": "gaming gift",
    "رسم": "drawing art set", "art": "drawing art set",
    "طبخ": "kitchen gadget gift", "cooking": "kitchen gadget gift",
    "رياضة": "sports gift", "sport": "sports gift",
    "قراءة": "book gift set", "reading": "book gift set",
    "موسيقى": "music gift headphones", "music": "music gift headphones",
    "تصوير": "camera photography gift", "photography": "camera photography gift",
    "تكنولوجيا": "tech gadget gift", "tech": "tech gadget gift",
}


async def smart_gift_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point via /gift command or menu button."""
    await set_user_state(update.effective_user.id, "smart_gift")
    await update.message.reply_text(GIFT_PROMPT, parse_mode="Markdown")


async def handle_smart_gift_text(update, context, text: str):
    user_id = update.effective_user.id
    await set_user_state(user_id, "idle")

    allowed, reason = await can_search(user_id)
    if not allowed:
        await update.message.reply_text(f"🔒 {reason}")
        return

    msg = await update.message.reply_text("🎁 جاري التفكير في أفضل هدية...")

    age_match = re.search(r"(\d{1,2})\s*(سنة|سنين|عام|years?)", text, re.IGNORECASE)
    age = int(age_match.group(1)) if age_match else None

    search_term = None
    text_lower = text.lower()
    for kw, mapped in INTEREST_MAP.items():
        if kw in text_lower:
            search_term = mapped
            break

    if not search_term:
        # fallback: use the raw text as the search query, prefixed with "gift"
        search_term = f"gift {text}"

    results = await multi_store_search(search_term)
    await increment_search_count(user_id)

    from utils.database import get_user_currency
    from utils.currency import convert_results_to_currency
    user_currency = await get_user_currency(user_id)
    results = await convert_results_to_currency(results, user_currency)

    # Keep only results with a real price, prefer higher rating
    priced = [r for r in results if r.get("price", 0) > 0]
    if not priced:
        await msg.edit_text(
            "❌ لم أجد هدايا مناسبة بهذا الوصف. جرب وصفاً مختلفاً أو اذكر اهتماماً أوضح "
            "(مثل: ألعاب، رسم، رياضة، طبخ، تصوير)."
        )
        return

    priced.sort(key=lambda r: r.get("rating", 0), reverse=True)
    top_picks = priced[:3]

    age_line = f" لشخص عمره {age} سنة" if age else ""
    lines = [
        f"🎁 *اقتراحات هدايا{age_line}*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, p in enumerate(top_picks, 1):
        lines.append(format_product_card(p, rank=i))
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")

    kb_rows = [[InlineKeyboardButton(
        f"🛒 اشتري الخيار {i+1}", url=apply_affiliate(p["url"], p["store"])
    )] for i, p in enumerate(top_picks)]
    kb_rows.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")])

    await msg.edit_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb_rows),
        disable_web_page_preview=True
    )
