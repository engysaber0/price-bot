"""
Subscription plans handler.
Stripe integration is stubs until STRIPE_SECRET_KEY is configured.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.settings import settings
from utils.database import get_user


PLANS_TEXT = (
    "💳 *خطط الاشتراك*\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "🆓 *الخطة المجانية*\n"
    f"   • {settings.FREE_SEARCHES_PER_DAY} عمليات بحث يومياً\n"
    "   • مقارنة الأسعار الأساسية\n"
    "   • كوبونات الخصم\n\n"
    f"⭐ *الباقة الأساسية — {settings.BASIC_PRICE_USD}$/شهر*\n"
    f"   • {settings.BASIC_SEARCHES_PER_DAY} عملية بحث يومياً\n"
    "   • وكيل الشراء الذكي\n"
    "   • تنبيهات الأسعار\n"
    "   • البحث بالصورة\n\n"
    f"🚀 *الباقة الاحترافية — {settings.PRO_PRICE_USD}$/شهر*\n"
    "   • بحث غير محدود\n"
    "   • أولوية في النتائج\n"
    "   • تنبيهات غير محدودة\n"
    "   • دعم مباشر\n"
    "━━━━━━━━━━━━━━━━━━━━━━"
)


async def subscription_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await get_user(update.effective_user.id)
    current = user["plan"] if user else "free"
    plan_ar = {"free": "مجانية", "basic": "أساسية ⭐", "pro": "احترافية 🚀"}.get(current, "مجانية")

    text = PLANS_TEXT + f"\n\n✅ خطتك الحالية: *{plan_ar}*"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ اشترك في الأساسية — 1$/شهر", callback_data="sub:basic")],
        [InlineKeyboardButton("🚀 اشترك في الاحترافية — 3$/شهر", callback_data="sub:pro")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def show_subscription(query, context):
    user = await get_user(query.from_user.id)
    current = user["plan"] if user else "free"
    plan_ar = {"free": "مجانية", "basic": "أساسية ⭐", "pro": "احترافية 🚀"}.get(current, "مجانية")

    text = PLANS_TEXT + f"\n\n✅ خطتك الحالية: *{plan_ar}*"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ اشترك في الأساسية — 1$/شهر", callback_data="sub:basic")],
        [InlineKeyboardButton("🚀 اشترك في الاحترافية — 3$/شهر", callback_data="sub:pro")],
        [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")],
    ])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def handle_sub_callback(query, context, data: str):
    plan = data.split(":")[1]  # basic | pro
    price = settings.BASIC_PRICE_USD if plan == "basic" else settings.PRO_PRICE_USD
    plan_ar = "الأساسية ⭐" if plan == "basic" else "الاحترافية 🚀"

    if not settings.STRIPE_SECRET_KEY:
        # Manual payment fallback
        await query.edit_message_text(
            f"💳 *الاشتراك في الباقة {plan_ar}*\n\n"
            f"السعر: *{price}$/شهر*\n\n"
            "للدفع، تواصل مع المسؤول وأرسل له:\n"
            f"• اسم المستخدم: `{query.from_user.username or query.from_user.id}`\n"
            f"• الباقة: {plan_ar}\n\n"
            "سيتم تفعيل الاشتراك خلال 24 ساعة. ✅",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="menu:subscription")
            ]])
        )
        return

    # Stripe payment link (requires Stripe setup)
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": f"Price Bot - {plan_ar}"},
                    "unit_amount": int(price * 100),
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url="https://t.me/YourBotUsername",
            cancel_url="https://t.me/YourBotUsername",
            metadata={"user_id": str(query.from_user.id), "plan": plan},
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 ادفع الآن", url=session.url)
        ]])
        await query.edit_message_text(
            f"✅ لإتمام الاشتراك في *{plan_ar}*، اضغط الزر:",
            parse_mode="Markdown",
            reply_markup=kb
        )
    except Exception as e:
        await query.answer("❌ خطأ في الدفع. تواصل مع المسؤول.", show_alert=True)
