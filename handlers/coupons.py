"""Coupons display handler."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config.settings import settings


def _build_coupon_text() -> str:
    if not settings.COUPONS:
        return "🎟 لا توجد كوبونات متاحة حالياً."

    lines = ["🎟 *كوبونات الخصم المتاحة*", "━━━━━━━━━━━━━━━━━━━━━━", ""]
    store_icons = {"NOON": "🟡", "AMAZON": "📦", "ALIEXPRESS": "🛍️"}

    for store, code, discount in settings.COUPONS:
        icon = store_icons.get(store, "🏪")
        lines.append(f"{icon} *{store}*")
        lines.append(f"   كود: `{code}`")
        lines.append(f"   خصم: *{discount}*")
        lines.append("")

    lines.append("💡 انسخ الكود واستخدمه عند الدفع!")
    return "\n".join(lines)


async def coupons_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")
    ]])
    await update.message.reply_text(_build_coupon_text(), parse_mode="Markdown", reply_markup=kb)


async def show_coupons(query, context):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")
    ]])
    await query.edit_message_text(_build_coupon_text(), parse_mode="Markdown", reply_markup=kb)
