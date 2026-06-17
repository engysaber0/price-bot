"""
Price alerts: set target price → bot notifies when price drops.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.database import (
    add_price_alert, get_active_alerts, deactivate_alert,
    get_user_alerts, get_user
)
from scrapers.search_engine import multi_store_search

logger = logging.getLogger(__name__)


async def alerts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_alerts_menu_message(update.message)


async def show_alerts_menu(query, context):
    user_id = query.from_user.id
    alerts = await get_user_alerts(user_id)

    if not alerts:
        text = (
            "🔔 *تنبيهات الأسعار*\n\n"
            "لا توجد تنبيهات نشطة حالياً.\n\n"
            "عند البحث عن منتج، اضغط زر 🔔 لإضافة تنبيه."
        )
    else:
        lines = ["🔔 *تنبيهاتك النشطة:*", ""]
        for a in alerts:
            lines.append(
                f"• *{a['product_name'][:30]}*\n"
                f"  🎯 السعر المستهدف: {a['target_price']:,.0f} {a['currency']}\n"
                f"  💰 السعر الحالي: {a['current_price']:,.0f} {a['currency']}\n"
            )
        text = "\n".join(lines)

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu:main")
    ]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)


async def show_alerts_menu_message(message):
    user_id = message.from_user.id
    alerts = await get_user_alerts(user_id)

    if not alerts:
        text = (
            "🔔 *تنبيهات الأسعار*\n\n"
            "لا توجد تنبيهات نشطة.\n\n"
            "عند البحث عن منتج، اضغط 🔔 لإضافة تنبيه."
        )
    else:
        lines = ["🔔 *تنبيهاتك النشطة:*", ""]
        for a in alerts:
            lines.append(
                f"• *{a['product_name'][:30]}*\n"
                f"  🎯 المستهدف: {a['target_price']:,.0f} {a['currency']}\n"
                f"  💰 الحالي: {a['current_price']:,.0f} {a['currency']}\n"
            )
        text = "\n".join(lines)

    await message.reply_text(text, parse_mode="Markdown")


async def handle_alert_callback(query, context, data: str):
    """Handles alert:set:{alert_idx} callbacks. The actual product name/price
    are looked up from context.user_data (set when the search results were
    shown) since Telegram caps callback_data at 64 bytes — too small for
    Arabic product names."""
    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("بيانات التنبيه غير صالحة.")
        return

    alert_idx = parts[2]
    pending_alerts = context.user_data.get("pending_alerts", {})
    alert_info = pending_alerts.get(alert_idx)

    if not alert_info:
        await query.answer("⚠️ انتهت صلاحية هذا الزر، يرجى البحث مرة أخرى.", show_alert=True)
        return

    store = alert_info["store"]
    current_price = alert_info["price"]
    product_name = alert_info["query"]
    target_price = current_price * 0.9  # default 10% drop

    from utils.database import get_user_currency
    user_currency = await get_user_currency(query.from_user.id)

    await add_price_alert(
        user_id=query.from_user.id,
        product_name=product_name,
        target_price=target_price,
        current_price=current_price,
        store=store,
        currency=user_currency,
    )
    await query.answer(f"✅ تم ضبط التنبيه عند {target_price:,.0f} {user_currency}!", show_alert=True)


async def check_price_alerts(context: ContextTypes.DEFAULT_TYPE):
    """Job that runs every 6 hours to check all active price alerts."""
    alerts = await get_active_alerts()
    logger.info(f"Checking {len(alerts)} price alerts...")

    for alert in alerts:
        try:
            results = await multi_store_search(alert["product_name"])
            # Find price from same store
            store_results = [r for r in results if r.get("store") == alert["store"]]
            if not store_results:
                store_results = results

            if not store_results:
                continue

            new_price = store_results[0]["price"]

            if new_price <= alert["target_price"]:
                from utils.affiliate import apply_affiliate
                aff_url = apply_affiliate(store_results[0].get("url", "#"), alert["store"])
                text = (
                    f"🎉 *انخفض السعر!*\n\n"
                    f"📦 {alert['product_name']}\n"
                    f"💰 السعر الجديد: *{new_price:,.0f} {alert['currency']}*\n"
                    f"🎯 سعرك المستهدف: {alert['target_price']:,.0f} {alert['currency']}\n"
                    f"💸 وفّرت: {alert['current_price'] - new_price:,.0f} {alert['currency']}\n\n"
                    f"🔗 [اشتري الآن]({aff_url})"
                )
                await context.bot.send_message(
                    chat_id=alert["user_id"],
                    text=text,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
                await deactivate_alert(alert["id"])
                logger.info(f"Alert {alert['id']} fired for user {alert['user_id']}")

        except Exception as e:
            logger.error(f"Error checking alert {alert['id']}: {e}")