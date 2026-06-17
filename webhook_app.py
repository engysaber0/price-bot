import asyncio
import logging
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import BOT_TOKEN
from models.database import init_db
from handlers.start import start_handler, get_main_keyboard, MAIN_MENU_TEXT
from handlers.compare import get_compare_handler
from handlers.fake_detector import get_fake_detector_handler
from handlers.compare_two import get_compare_two_handler
from handlers.image_search import get_image_search_handler
from handlers.coupons import get_coupons_handler
from handlers.smart_agent import get_smart_agent_handler
from handlers.alerts import get_alerts_handler, check_alerts_job
from handlers.gifts import get_gifts_handler
from handlers.referral import get_referral_handler
from handlers.subscription import get_subscription_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()
bot_app = None

async def main_menu_callback(update: Update, context):
    q = update.callback_query
    await q.answer()
    await q.message.edit_text(
        MAIN_MENU_TEXT,
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown",
    )

async def build_bot():
    global bot_app
    bot_app = Application.builder().token(BOT_TOKEN).updater(None).build()

    bot_app.add_handler(CommandHandler("start", start_handler))
    bot_app.add_handler(CommandHandler("menu", start_handler))
    bot_app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^main_menu$"))
    bot_app.add_handler(get_compare_handler())
    bot_app.add_handler(get_fake_detector_handler())
    bot_app.add_handler(get_compare_two_handler())
    bot_app.add_handler(get_image_search_handler())
    bot_app.add_handler(get_smart_agent_handler())
    bot_app.add_handler(get_alerts_handler())
    bot_app.add_handler(get_gifts_handler())
    for handler in get_coupons_handler():
        bot_app.add_handler(handler)
    for handler in get_referral_handler():
        bot_app.add_handler(handler)
    for handler in get_subscription_handler():
        bot_app.add_handler(handler)

    await init_db()
    await bot_app.initialize()
    await bot_app.start()
    logger.info("Bot initialized.")

@app.on_event("startup")
async def startup():
    await build_bot()

@app.on_event("shutdown")
async def shutdown():
    if bot_app:
        await bot_app.stop()

@app.get("/")
async def root():
    return {"status": "Bot is running!"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)
    await bot_app.process_update(update)
    return {"ok": True}
