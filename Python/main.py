"""
Основной модуль бота telegram
python-telegram-bot
"""
import sys
import logging
import traceback
from warnings import filterwarnings
from datetime import datetime
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler, PicklePersistence
from telegram import User, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.warnings import PTBUserWarning
import config as cfg
from schedule_parser import School, Department, SchoolClass
from week_pdf_parser import Lesson, WeekSchedule
from data import MenuData, create_context_data, get_school_object, get_school, IntervalError
from data import DEPARTMENT_OBJECT, CLASS_OBJECT, WEEK_SCHEDULE_OBJECT, WEEK_OBJECT, DAY_OF_WEEK_OBJECT, LESSONS_OBJECT
from database import save_user_class, get_user_class, save_error
import messages

START_ROUTES, END_ROUTES = range(2)

async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправка сообщения
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text=messages.HELLO_MESSAGE)

def keyboard_button_school(update: Update, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Добавление кнопки расписание школы
    """
    keyboard = [
        [InlineKeyboardButton(messages.SCHEDULE_MESSAGE, callback_data="SCHOOL")],
    ]

    user_id = update.effective_user.id
    class_id = get_user_class(user_id)
    if class_id is not None:
        school: School = get_school(context, user_id)
        class_: SchoolClass = school.get_class_by_id(class_id)
        if class_ is not None:
            button = [InlineKeyboardButton(class_.name, callback_data=MenuData(class_.department.id, class_.id).to_string(CLASS_OBJECT))]
            keyboard.append(button)

    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправить сообщение, когда выполнена команда /start.
    """
    user: User = update.effective_user
    logging.info(f"command start for {user.id}")
    reply_markup: InlineKeyboardMarkup = keyboard_button_school(update, context)
    create_context_data(context, user.id)

    await update.message.reply_text(
        f"Привет {user.first_name}! \n{messages.HELLO_MESSAGE}\nИспользуй меню <Расписание> для получения текущего расписания уроков",
        reply_markup=reply_markup,
    )
    return START_ROUTES

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправить сообщение, когда выполнена команда /help.
    """
    user: User = update.effective_user
    logging.info(f"command help for {user.id}")
    reply_markup: InlineKeyboardMarkup = keyboard_button_school(update, context)
    create_context_data(context, user.id)

    await update.message.reply_text(
        "\start - Начало работы бота\n\help - Список команд\n\about - Описание бота",
        reply_markup=reply_markup,
    )
    return START_ROUTES

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправить сообщение, когда выполнена команда /help.
    """
    user: User = update.effective_user
    logging.info(f"command help for {user.id}")
    reply_markup: InlineKeyboardMarkup = keyboard_button_school(update, context)
    create_context_data(context, user.id)

    await update.message.reply_text(
        f"{messages.HELLO_MESSAGE}\nЗамечания и предложения по работе бота можно направлять на почту vladimir2.01.0.za@gmail.com",
        reply_markup=reply_markup,
    )
    return START_ROUTES

def keyboard_button_departments(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> any:
    """
    Добавление кнопок корпусов
    """
    school: School
    school, error_message = get_school_object(DEPARTMENT_OBJECT, menu_data, context)
    if error_message:
        return None, error_message
    keyboard = []
    department: Department
    for department in school.departments:
        button = [InlineKeyboardButton(department.name, callback_data=MenuData(department.id).to_string(DEPARTMENT_OBJECT))]
        keyboard.append(button)
    keyboard.append([InlineKeyboardButton(messages.BACK_MESSAGE, callback_data=MenuData().to_string(DEPARTMENT_OBJECT))])
    return InlineKeyboardMarkup(keyboard), None

async def school_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка получения расписания школы
    """
    logging.info("command school")
    query = update.callback_query
    await query.answer()

    menu_data: MenuData = MenuData.from_string(DEPARTMENT_OBJECT, query.data)
    reply_markup, error_message = keyboard_button_departments(menu_data, context)
    if error_message:
        await query.edit_message_text(error_message)
        return START_ROUTES
    await query.edit_message_text(messages.CHOICE_DEPARTMENT_MESSAGE, reply_markup=reply_markup)
    return START_ROUTES

def keyboard_button_classes(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Получение списка классов для корпуса department_index
    """
    department: Department
    department, error_message = get_school_object(CLASS_OBJECT, menu_data, context)
    if error_message:
        return None, error_message

    keyboard = []
    class_: SchoolClass
    for class_ in department.class_list:
        button = [InlineKeyboardButton(class_.name, callback_data=MenuData(menu_data.department, class_.id).to_string(CLASS_OBJECT))]
        keyboard.append(button)
    keyboard.append([InlineKeyboardButton(messages.BACK_MESSAGE, callback_data=MenuData().to_string(CLASS_OBJECT))])
    return InlineKeyboardMarkup(keyboard), None

async def department_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора корпуса
    """
    logging.info("command department")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string(DEPARTMENT_OBJECT, query.data)
    if menu_data.department == -1:
        # Нажата кнопка возврата
        reply_markup = keyboard_button_school(update, context)
        await query.edit_message_text(messages.HELLO_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Нажата кнопка корпуса
        reply_markup, error_message = keyboard_button_classes(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(messages.CHOICE_CLASS_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES

def keyboard_button_day_of_week(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Получение списка дней недели для MenuData
    """
    day_of_week_list: list
    day_of_week_list, error_message = get_school_object(DAY_OF_WEEK_OBJECT, menu_data, context)
    if error_message:
        return None, error_message
    week_list, error_message = get_school_object(WEEK_OBJECT, menu_data, context)
    if error_message:
        return None, error_message

    keyboard = []
    for index, week_day in enumerate(day_of_week_list):
        button = [InlineKeyboardButton(week_day, callback_data=MenuData(menu_data.department, menu_data.class_, menu_data.week, index).to_string(DAY_OF_WEEK_OBJECT))]
        keyboard.append(button)
    if len(week_list) > 1:
        keyboard.append([InlineKeyboardButton(f"{messages.BACK_MESSAGE} к N недели", callback_data=MenuData(menu_data.department, menu_data.class_, -2).to_string(DAY_OF_WEEK_OBJECT))])
    keyboard.append([InlineKeyboardButton(f"{messages.BACK_MESSAGE} к классам", callback_data=MenuData(menu_data.department, menu_data.class_, -1).to_string(DAY_OF_WEEK_OBJECT))])
    return InlineKeyboardMarkup(keyboard), None

def keyboard_button_week(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Получение списка недель месяца для MenuData
    """
    week_list: list
    week_list, error_message = get_school_object(WEEK_OBJECT, menu_data, context)
    if error_message:
        return None, error_message

    if len(week_list) == 1:
        return keyboard_button_day_of_week(MenuData(menu_data.department, menu_data.class_, 1), context)
    elif len(week_list) > 1:
        keyboard = []
        for week in week_list:
            button = [InlineKeyboardButton(f"Неделя месяца {week}", callback_data=MenuData(menu_data.department, menu_data.class_, week).to_string(WEEK_OBJECT))]
            keyboard.append(button)
        keyboard.append([InlineKeyboardButton(messages.BACK_MESSAGE, callback_data=MenuData(menu_data.department, -1).to_string(WEEK_OBJECT))])
        return InlineKeyboardMarkup(keyboard), None
    else:
        return "Ошибка получения списка недель", None

async def class_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора класса
    """
    logging.info("command class")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string(CLASS_OBJECT, query.data)
    if menu_data.department == -1:
        # Нажата кнопка возврата
        reply_markup, error_message = keyboard_button_departments(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(text=messages.CHOICE_DEPARTMENT_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Запросить список недель месяца
        reply_markup, error_message = keyboard_button_week(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(messages.CHOICE_WEEK_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES

async def week_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора недели месяца
    """
    logging.info("command week")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string(WEEK_OBJECT, query.data)
    if menu_data.class_ == -1:
        # Нажата кнопка возврата к классам
        reply_markup, error_message = keyboard_button_classes(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(messages.CHOICE_CLASS_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Запросить дни недели расписания
        reply_markup, error_message = keyboard_button_day_of_week(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(messages.CHOICE_DAY_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    return START_ROUTES

async def day_of_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора дня недели месяца
    """
    logging.info("command day of week")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string(DAY_OF_WEEK_OBJECT, query.data)
    if menu_data.week == -1:
        # Нажата кнопка возврата к классам
        reply_markup, error_message = keyboard_button_classes(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(messages.CHOICE_CLASS_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    elif menu_data.week == -2:
        # Нажата кнопка возврата к неделям месяца
        reply_markup, error_message = keyboard_button_week(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(messages.CHOICE_WEEK_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Отобразить расписание
        lessons: Lesson
        lessons, error_message = get_school_object(LESSONS_OBJECT, menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        week_schedule: WeekSchedule
        week_schedule, error_message = get_school_object(WEEK_SCHEDULE_OBJECT, menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES

        user_id = update.effective_user.id
        class_id = week_schedule.school_class.id
        user_name = update.effective_user.full_name
        save_user_class(user_id, class_id, user_name)

        message = f"Расписание для класса {week_schedule.school_class.name}/{week_schedule.school_class.department.name}\n{week_schedule.school_class.link}\n"
        day_of_week_list = week_schedule.day_of_week_list(menu_data.week)
        message = f"{message}\n{day_of_week_list[menu_data.day_of_week]}:\n"
        lesson: Lesson
        for lesson in lessons:
            lesson_string = lesson.to_str(parse_mode = ParseMode.HTML)
            message += f"{lesson_string}\n"
        await query.edit_message_text(message, parse_mode=ParseMode.HTML)
        return START_ROUTES

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработка ошибок
    """
    logging.error("Exception:", exc_info=context.error)
    if isinstance(context.error, IntervalError):
        logging.error("Ignore exception IntervalError")
        return

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = "An exception was raised while handling an update\n" + \
        f"update = {update_str}\n" + \
        f"context.chat_data = {str(context.bot_data)}\n" + \
        f"context.chat_data = {str(context.chat_data)}\n" + \
        f"context.user_data = {str(context.user_data)}\n" + \
        f"traceback = {tb_string}"
    logging.error(f"Error info:{message}")
    user_id = 0
    if hasattr(update, 'effective_user') and update.effective_user is not None:
        user_id = update.effective_user.id
    save_error(user_id, tb_string, str(update_str), str(context.chat_data), str(context.user_data))

async def job_handler(context: ContextTypes.DEFAULT_TYPE)-> None:
    """
    Периодически выполняемое задание
    """
    now = datetime.now()
    current_time = now.strftime("%d/%m/%Y %H:%M:%S")
    logging.info(f"job_handler {current_time}")
    school: School = get_school(context, 0)
    parse_info = school.last_parse_info
    logging.info(f"last parse error: {parse_info}")

def main() -> None:
    """
    Запуск бота
    """
    # Запуск логирования
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    cfg.disable_logger(["httpcore.connection", "httpcore.http11"])
    cfg.disable_logger(["pdfminer.psparser", "pdfminer.pdfparser", "pdfminer.pdfinterp", "pdfminer.cmapdb", "pdfminer.pdfdocument", "pdfminer.pdfpage"])
    logging.info("Start bot")
    db_path = cfg.get_data_path()
    file_path = f"{db_path}/bot_persistence"
    persistence = PicklePersistence(filepath=file_path, update_interval = 50)
    application = Application.builder().token(cfg.BOT_TOKEN).persistence(persistence)   \
        .read_timeout(30)  \
        .write_timeout(30) \
        .build()

    filterwarnings(action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_message))
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("help", help),
            CommandHandler("about", about),
        ],
        states={
            START_ROUTES: [
                CallbackQueryHandler(school_button, pattern="^SCHOOL"),
                CallbackQueryHandler(department_button, pattern="^DEPARTMENT*"),
                CallbackQueryHandler(class_button, pattern="^CLASS*"),
                CallbackQueryHandler(week_button, pattern="^WEEK*"),
                CallbackQueryHandler(day_of_week, pattern="^DAY_OF_WEEK*")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
        name="bot_conversation",
        persistent=True,
    )
    application.add_handler(conv_handler)
    job_queue = application.job_queue
    job_queue.run_repeating(job_handler, interval=60*60*12, first=10)

    # обработчик ошибок
    application.add_error_handler(error_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
