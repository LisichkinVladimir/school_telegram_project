"""
Основной модуль бота telegram
python-telegram-bot
"""
import sys
import logging
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import config as cfg
from schedule_parser import Schedules, Schedule, SchoolClass
from data import create_schedules, get_schedules

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
    create_schedules(context)

    await update.message.reply_text(
        f"Привет {user.first_name}! \n{HELLO_MESSAGE}\nИспользуй меню <Расписание> для получения текущего расписания уроков",
        reply_markup=reply_markup,
    )
    return START_ROUTES

def keyboard_button_departments(context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Добавление кнопок корпусов
    """
    schedules: Schedules = get_schedules(context)
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
        await query.edit_message_text(HELLO_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Нажата кнопка корпуса
        schedules: Schedules = get_schedules(context)
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
            button = [InlineKeyboardButton(class_.name, callback_data="CLASS"+command+'_'+str(index))]
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
        await query.edit_message_text(text="Выберете корпус:", reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Разбор pdf файла недельного расписания
        schedules: Schedules = get_schedules(context)
        if schedules is None:
            await query.edit_message_text("Список корпусов не определен")
            return START_ROUTES
        index = command.find("_")
        if index == -1 or not command[0:index].isnumeric() or not command[index+1:].isnumeric():
            await query.edit_message_text("Индекс не корректен")
            return START_ROUTES
        schedule_index = int(command[0:index])
        class_index = int(command[index+1:])
        if schedule_index < 0 or schedule_index > len(schedules.list)-1:
            await query.edit_message_text("Индекс корпуса не корректен")
            return START_ROUTES
        schedule: Schedule = schedules.list[schedule_index]
        if class_index < 0 or class_index > len(schedule.class_list)-1:
            await query.edit_message_text("Индекс класса не корректен")
            return START_ROUTES
        school_class: SchoolClass = schedule.class_list[class_index]
        url = cfg.BASE_URL + "/" + school_class.link
        await query.edit_message_text(f"Расписание класса: {url}")
        return START_ROUTES

def main() -> None:
    """
    Запуск бота
    """
    # Запуск логирования
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.info("Start bot")
    application = Application.builder().token(cfg.BOT_TOKEN).build()

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
