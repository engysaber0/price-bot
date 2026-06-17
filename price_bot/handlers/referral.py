"""
Referral system handler.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import get_user, get_or_create_user, add_points, redeem_points
from config.settings import settings


async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = await get_or_create_user(user.id, user.username or "", user.full_name or "")
    await _send_referral_card(update.message.reply_text, db_user, user.id)


async def show_referral(query, context):
    db_user = await get_user(query.from_user.id)
    if not db_user:
        await query.answer("حدث خطأ. أعد تشغيل /start")
        return
    await _send_referral_card(query.edit_message_text, db_user, query.from_user.id)


async def _send_referral_card(send_fn, db_user: dict, user_id: int):
    bot_username = "YourBotUsername"  # replace with real username at runtime
    ref_code = db_user["referral_code"]
    ref_url = f"https://t.me/{bot_username}?start=ref_{ref_code}"
    points = db_user["points"]
    ref_count = db_user["referral_count"]

    # Progress to next milestone
    milestones = [1, 5, 10, 50]
    next_milestone = next((m for m in milestones if m > ref_count), 50)
    progress = min(ref_count, next_milestone)

    text = (
        f"🎁 *نظام الإحالات*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 *رابطك الخاص:*\n`{ref_url}`\n\n"
        f"👥 أصدقاؤك: *{ref_count}*  |  🏆 نقاطك: *{points}*\n\n"
        f"*المكافآت:*\n"
        f"{'✅' if ref_count >= 1  else '⬜'} 1  صديق = 3 نقاط\n"
        f"{'✅' if ref_count >= 5  else '⬜'} 5  أصدقاء = 10 نقاط\n"
        f"{'✅' if ref_count >= 10 else '⬜'} 10 أصدقاء = 50 نقطة\n"
        f"{'✅' if ref_count >= 50 else '⬜'} 50 صديقاً = 100 نقطة\n\n"
        f"*استبدال النقاط:*\n"
        f"🔹 50 نقطة = 10 بحث إضافي\n"
        f"🔹 100 نقطة = 20 بحث إضافي\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    kb_rows = []
    if points >= 50:
        kb_rows.append([InlineKeyboardButton("🎁 استبدل 50 نقطة (10 بحث)", callback_data="redeem:50:10")])
    if points >= 100:
        kb_rows.append([InlineKeyboardButton("🎁 استبدل 100 نقطة (20 بحث)", callback_data="redeem:100:20")])
    kb_rows.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")])

    await send_fn(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb_rows))


async def handle_redeem_callback(query, context, data: str):
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("بيانات غير صالحة")
        return
    _, points_str, searches_str = parts
    points = int(points_str)
    searches = int(searches_str)

    success = await redeem_points(query.from_user.id, points, searches)
    if success:
        await query.answer(f"✅ تم استبدال {points} نقطة بـ {searches} بحث إضافي!", show_alert=True)
    else:
        await query.answer("❌ نقاطك غير كافية.", show_alert=True)
