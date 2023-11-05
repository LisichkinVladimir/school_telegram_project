"""
Основной модуль бота telegram
"""
import logging
import sys
from telegram.ext import Application, ContextTypes, CommandHandler
from telegram import ForceReply, Update
import config as cfg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    logging.info("command start")
    user = update.effective_user    
    await update.message.reply_html(
        rf"Привет {user.mention_html()}!\nБот школьное_расписание предназначен для удобства школьников школы 1502 и получения свежей информации об изменении расписания",
        reply_markup=ForceReply(selective=True),
    )

def main() -> None:
    """Start the bot"""
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    application = Application.builder().token(cfg.BOT_TOKEN).build()
    logging.info(f"Start bot")

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
