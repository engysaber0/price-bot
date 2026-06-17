"""Fake product detector via text or URL."""
from telegram import Update
from telegram.ext import ContextTypes
from utils.database import set_user_state


async def fake_detector_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_user_state(update.effective_user.id, "fake_detect")
    await update.message.reply_text(
        "⚠️ *كشف المنتجات المقلدة*\n\n"
        "أرسل لي رابط المنتج أو اسمه وسأحلل له مستوى الخطر.",
        parse_mode="Markdown"
    )
