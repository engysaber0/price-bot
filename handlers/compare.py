"""Compare two products handler - delegates to search.py"""
from telegram import Update
from telegram.ext import ContextTypes
from utils.database import set_user_state


async def compare_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_user_state(update.effective_user.id, "compare_two")
    await update.message.reply_text(
        "⚔️ أرسل اسمَي المنتجَين مفصولَين بـ `vs`\n\nمثال: `iPhone 15 vs Galaxy S24`",
        parse_mode="Markdown"
    )
