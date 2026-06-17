"""Smart agent handler - sets state and prompts user."""
from telegram import Update
from telegram.ext import ContextTypes
from utils.database import set_user_state


async def smart_agent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await set_user_state(update.effective_user.id, "smart_agent")
    await update.message.reply_text(
        "🤖 *وكيل الشراء الذكي*\n\n"
        "أخبرني بميزانيتك واحتياجك:\n\n"
        "مثال:\n"
        "• _معي 500 دولار وأريد أفضل لابتوب للبرمجة_\n"
        "• _أريد هاتف للتصوير بـ 300 دولار_\n"
        "• _هدية لشخص عمره 25 سنة يحب الألعاب_",
        parse_mode="Markdown"
    )
