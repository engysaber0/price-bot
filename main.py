#!/usr/bin/env python3
"""
Price Comparison Telegram Bot - Main Entry Point
"""
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
from config.settings import settings
from handlers.start import start_handler, help_handler
from handlers.search import search_handler
from handlers.compare import compare_handler
from handlers.fake_detector import fake_detector_handler
from handlers.image_search import image_search_handler
from handlers.coupons import coupons_handler
from handlers.smart_agent import smart_agent_handler
from handlers.smart_gift import smart_gift_handler
from handlers.alerts import alerts_handler, check_price_alerts
from handlers.referral import referral_handler
from handlers.subscription import subscription_handler
from handlers.menu import menu_callback_handler
from utils.database import init_db

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "❌ حدث خطأ مؤقت. يرجى المحاولة مرة أخرى."
        )


async def post_init(application: Application) -> None:
    await init_db()
    logger.info("✅ Database initialized")


def main() -> None:
    app = Application.builder().token(settings.BOT_TOKEN).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("referral", referral_handler))
    app.add_handler(CommandHandler("subscribe", subscription_handler))
    app.add_handler(CommandHandler("coupons", coupons_handler))
    app.add_handler(CommandHandler("alerts", alerts_handler))
    app.add_handler(CommandHandler("gift", smart_gift_handler))

    # Callback buttons (inline keyboards)
    app.add_handler(CallbackQueryHandler(menu_callback_handler))

    # Photo/image messages
    app.add_handler(MessageHandler(filters.PHOTO, image_search_handler))

    # Text messages (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_handler))

    # Error handler
    app.add_error_handler(error_handler)

    # Job queue - check price alerts every 6 hours
    app.job_queue.run_repeating(check_price_alerts, interval=21600, first=60)

    logger.info("🤖 Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
