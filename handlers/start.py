"""
/start command + help
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import get_or_create_user, process_referral


MAIN_MENU = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🔍 مقارنة الأسعار", callback_data="menu:compare_prices"),
        InlineKeyboardButton("⚠️ كشف التقليد",    callback_data="menu:fake_detect"),
    ],
    [
        InlineKeyboardButton("⚔️ مقارنة منتجين",  callback_data="menu:compare_two"),
        InlineKeyboardButton("📸 بحث بالصورة",    callback_data="menu:image_search"),
    ],
    [
        InlineKeyboardButton("🎟 كوبونات الخصم",  callback_data="menu:coupons"),
        InlineKeyboardButton("🤖 وكيل الشراء",    callback_data="menu:smart_agent"),
    ],
    [
        InlineKeyboardButton("🔔 تنبيهات الأسعار", callback_data="menu:alerts"),
        InlineKeyboardButton("🎁 هدية ذكية",      callback_data="menu:smart_gift"),
    ],
    [
        InlineKeyboardButton("🎉 نظام الإحالات",  callback_data="menu:referral"),
        InlineKeyboardButton("💳 الاشتراكات",     callback_data="menu:subscription"),
    ],
])


WELCOME_TEXT = """
🤖 *أهلاً بك في بوت مقارنة الأسعار الذكي!*

أنا هنا أساعدك تشتري أذكى وتوفر أكتر 💰

*اختر من القائمة أدناه:*
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    tg_user = await get_or_create_user(
        user.id, user.username or "", user.full_name or "",
        language_code=user.language_code
    )

    # Handle referral link: /start ref_XXXXXX
    args = context.args
    if args and args[0].startswith("ref_"):
        ref_code = args[0][4:]
        pts = await process_referral(user.id, ref_code)
        if pts > 0:
            await update.message.reply_text(
                f"🎉 تم تسجيلك عبر رابط الإحالة! حصلت على {pts} نقاط كبداية."
            )

    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=MAIN_MENU,
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *كيفية الاستخدام:*\n\n"
        "• اكتب اسم المنتج مباشرة للبحث عن أفضل سعر\n"
        "• أو اضغط على الأزرار للاختيار\n\n"
        "*الأوامر:*\n"
        "/start — القائمة الرئيسية\n"
        "/referral — رابط الإحالة الخاص بك\n"
        "/alerts — تنبيهات الأسعار\n"
        "/coupons — أكواد الخصم\n"
        "/subscribe — الاشتراكات\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_MENU)
