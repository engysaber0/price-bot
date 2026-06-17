"""
Routes all InlineKeyboard callbacks from the main menu.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import set_user_state


BACK_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")]
])

PROMPTS = {
    "compare_prices": (
        "🔍 *مقارنة الأسعار*\n\n"
        "أرسل لي اسم المنتج أو وصفه وسأبحث لك في نون، أمازون، علي إكسبريس والمزيد!\n\n"
        "مثال: _سماعة بلوتوث أقل من 1000 جنيه_",
        "search"
    ),
    "fake_detect": (
        "⚠️ *كشف المنتجات المقلدة*\n\n"
        "أرسل لي رابط المنتج أو اسمه وسأحلل له مستوى الخطر.\n\n"
        "مثال: _رابط منتج من نون أو أمازون_",
        "fake_detect"
    ),
    "compare_two": (
        "⚔️ *مقارنة بين منتجين*\n\n"
        "أرسل اسمَي المنتجَين مفصولَين بـ vs\n\n"
        "مثال: _iPhone 15 vs Samsung Galaxy S24_",
        "compare_two"
    ),
    "image_search": (
        "📸 *البحث بالصورة*\n\n"
        "أرسل لي صورة المنتج وسأبحث عنه في المتاجر!",
        "image_search"
    ),
    "coupons": None,   # handled directly
    "smart_agent": (
        "🤖 *وكيل الشراء الذكي*\n\n"
        "أخبرني بميزانيتك واحتياجك وسأختار لك أفضل منتج!\n\n"
        "مثال: _معي 500 دولار وأريد أفضل لابتوب للبرمجة_",
        "smart_agent"
    ),
    "smart_gift": (
        "🎁 *القسم الذكي — اقتراح الهدايا*\n\n"
        "أخبرني عن الشخص (العمر + اهتماماته) وسأقترح له أفضل هدية!\n\n"
        "مثال:\n"
        "• _هدية لشخص عمره 25 سنة ويحب الألعاب_\n"
        "• _هدية لبنت عمرها 10 سنين تحب الرسم_",
        "smart_gift"
    ),
    "alerts": None,     # handled directly
    "referral": None,   # handled directly
    "subscription": None,  # handled directly
}


async def menu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu:main":
        from handlers.start import MAIN_MENU, WELCOME_TEXT
        await query.edit_message_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=MAIN_MENU)
        return

    if not data.startswith("menu:"):
        # delegate to specific handlers via stored state
        await _route_other(query, context, data)
        return

    section = data.split(":", 1)[1]

    if section == "coupons":
        from handlers.coupons import show_coupons
        await show_coupons(query, context)
        return

    if section == "alerts":
        from handlers.alerts import show_alerts_menu
        await show_alerts_menu(query, context)
        return

    if section == "referral":
        from handlers.referral import show_referral
        await show_referral(query, context)
        return

    if section == "subscription":
        from handlers.subscription import show_subscription
        await show_subscription(query, context)
        return

    prompt_info = PROMPTS.get(section)
    if prompt_info:
        text, state = prompt_info
        await set_user_state(query.from_user.id, state)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=BACK_BTN)
    else:
        await query.edit_message_text("❓ قسم غير معروف", reply_markup=BACK_BTN)


async def _route_other(query, context, data: str):
    """Handle non-menu callbacks like alert confirm, subscription buy, etc."""
    if data.startswith("alert:"):
        from handlers.alerts import handle_alert_callback
        await handle_alert_callback(query, context, data)
    elif data.startswith("sub:"):
        from handlers.subscription import handle_sub_callback
        await handle_sub_callback(query, context, data)
    elif data.startswith("redeem:"):
        from handlers.referral import handle_redeem_callback
        await handle_redeem_callback(query, context, data)
