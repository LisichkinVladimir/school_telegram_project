"""
Основной модуль бота telegram
python-telegram-bot
"""
import logging
import sys
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import config as cfg
from schedule_parser import Schedules

HELLO_MESSAGE = """Бот школьное_расписание предназначен для удобства школьников школы 1502 и получения свежей информации об изменении расписания\n
используй команду /start для начала работы бота"""

START_ROUTES, END_ROUTES = range(2)

async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправка сообщения
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text=HELLO_MESSAGE)

def keyboard_button_schedule() -> InlineKeyboardMarkup:
    """
    Добавление кнопки расписание
    """
    keyboard = [
        [InlineKeyboardButton("Расписание", callback_data="SCHEDULE")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправить сообщение, когда выполнена команда /start.
    """
    logging.info("command start")
    user = update.effective_user
    reply_markup = keyboard_button_schedule()
    context.user_data["schedules"] = None

    await update.message.reply_text(
        f"Привет {user.first_name}! \n{HELLO_MESSAGE}\nИспользуй меню <Расписание> для получения текущего расписания уроков",
        reply_markup=reply_markup,
    )
    return START_ROUTES

def keyboard_button_departments(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Добавление кнопок корпусов
    """
    schedules = context.user_data["schedules"]
    if schedules is None:
        schedules = Schedules()
        schedules.parse(cfg.SCHEDULE_URL)
        context.user_data["schedules"] = schedules
    keyboard = []
    index = 0
    for schedule in schedules.list:
        button = [InlineKeyboardButton(schedule.department, callback_data="DEPARTMENT"+str(index))]
        index += 1
        keyboard.append(button)
    keyboard.append([InlineKeyboardButton("<<Назад", callback_data="DEPARTMENT-1")])
    return InlineKeyboardMarkup(keyboard)

async def schedule_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка получения расписания
    """
    logging.info("command schedules")
    query = update.callback_query
    await query.answer()

    reply_markup = keyboard_button_departments(context)
    query = update.callback_query
    await query.edit_message_text(text="Выберете корпус:", reply_markup=reply_markup)
    return START_ROUTES

async def department_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора корпуса
    """
    logging.info("command department")
    query = update.callback_query
    await query.answer()
    command = query.data[10:]
    if command == "-1":
        # Нажата кнопка возврата
        reply_markup = keyboard_button_schedule()
        query = update.callback_query
        await query.edit_message_text(HELLO_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Нажата кнопка корпуса
        schedules: Schedules = context.user_data["schedules"]
        if schedules is None:
            await query.edit_message_text("Список корпусов не определен")
            return START_ROUTES
        if not command.isnumeric():
            await query.edit_message_text("Индекс корпуса не определен")
            return START_ROUTES
        index = int(command)
        if index < 0 or index > len(schedules.list)-1:
            await query.edit_message_text("Индекс корпуса не корректен")
            return START_ROUTES
        schedule = schedules.list[index]
        keyboard = []
        index = 0
        for class_ in schedule.class_list:
            button = [InlineKeyboardButton(class_.name, callback_data="CLASS"+str(index))]
            index += 1
            keyboard.append(button)
        keyboard.append([InlineKeyboardButton("<<Назад", callback_data="CLASS-1")])
        reply_markup = InlineKeyboardMarkup(keyboard)    
        query = update.callback_query
        await query.edit_message_text("Выберете класс", reply_markup=reply_markup)
        return START_ROUTES

async def class_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора класса
    """
    logging.info("command class")
    query = update.callback_query
    await query.answer()
    command = query.data[5:]
    if command == "-1":
        # Нажата кнопка возврата
        reply_markup = keyboard_button_departments(context)
        query = update.callback_query
        await query.edit_message_text(text="Выберете корпус:", reply_markup=reply_markup)
        return START_ROUTES

def main() -> None:
    """
    Запуск бота
    """
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    application = Application.builder().token(cfg.BOT_TOKEN).build()
    logging.info(f"Start bot")

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_message))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START_ROUTES: [
                CallbackQueryHandler(schedule_button, pattern="^SCHEDULE"),
                CallbackQueryHandler(department_button, pattern="^DEPARTMENT*"),
                CallbackQueryHandler(class_button, pattern="^CLASS*"),
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
