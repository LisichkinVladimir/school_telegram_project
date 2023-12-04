"""
Основной модуль бота telegram
python-telegram-bot
"""
import sys
import logging
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from telegram import User, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
import config as cfg
from schedule_parser import School, Department, SchoolClass
from week_pdf_parser import Lesson, WeekSchedule
from data import MenuData, create_school, get_school_object

HELLO_MESSAGE = """Бот школьное_расписание предназначен для удобства школьников школы 1502 и получения свежей информации об изменении расписания\n
используй команду /start для начала работы бота"""

START_ROUTES, END_ROUTES = range(2)

async def send_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправка сообщения
    """
    await context.bot.send_message(chat_id=update.effective_chat.id, text=HELLO_MESSAGE)

def keyboard_button_school() -> InlineKeyboardMarkup:
    """
    Добавление кнопки расписание школы
    """
    keyboard = [
        [InlineKeyboardButton("Школьное расписание", callback_data="SCHOOL")],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Отправить сообщение, когда выполнена команда /start.
    """
    user: User = update.effective_user
    logging.info(f"command start for {user.id}")
    reply_markup: InlineKeyboardMarkup = keyboard_button_school()
    create_school(context)

    await update.message.reply_text(
        f"Привет {user.first_name}! \n{HELLO_MESSAGE}\nИспользуй меню <Расписание> для получения текущего расписания уроков",
        reply_markup=reply_markup,
    )
    return START_ROUTES

def keyboard_button_departments(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> any:
    """
    Добавление кнопок корпусов
    """
    school: School
    school, error_message = get_school_object("DEPARTMENT", menu_data, context)
    if error_message:
        return None, error_message
    keyboard = []
    department: Department
    for department in school.departments:
        button = [InlineKeyboardButton(department.name, callback_data=MenuData(department.id).to_string("DEPARTMENT"))]
        keyboard.append(button)
    keyboard.append([InlineKeyboardButton("<<Назад", callback_data=MenuData().to_string("DEPARTMENT"))])
    return InlineKeyboardMarkup(keyboard), None

async def school_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка получения расписания школы
    """
    logging.info("command school")
    query = update.callback_query
    await query.answer()

    menu_data: MenuData = MenuData.from_string("DEPARTMENT", query.data)
    reply_markup, error_message = keyboard_button_departments(menu_data, context)
    if error_message:
        await query.edit_message_text(error_message)
        return START_ROUTES
    await query.edit_message_text(text="Выберете корпус:", reply_markup=reply_markup)
    return START_ROUTES

def keyboard_button_classes(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Получение списка классов для корпуса department_index
    """
    department: Department
    department, error_message = get_school_object("CLASS", menu_data, context)
    if error_message:
        return None, error_message

    keyboard = []
    class_: SchoolClass
    for class_ in department.class_list:
        button = [InlineKeyboardButton(class_.name, callback_data=MenuData(menu_data.department, class_.id).to_string("CLASS"))]
        keyboard.append(button)
    keyboard.append([InlineKeyboardButton("<<Назад", callback_data=MenuData().to_string("CLASS"))])
    return InlineKeyboardMarkup(keyboard), None

async def department_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора корпуса
    """
    logging.info("command department")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string("DEPARTMENT", query.data)
    if menu_data.department == -1:
        # Нажата кнопка возврата
        reply_markup = keyboard_button_school()
        await query.edit_message_text(HELLO_MESSAGE, reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Нажата кнопка корпуса
        reply_markup, error_message = keyboard_button_classes(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text("Выберете класс", reply_markup=reply_markup)
        return START_ROUTES

def keyboard_button_day_of_week(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Получение списка дней недели для MenuData
    """
    day_of_week_list: list
    day_of_week_list, error_message = get_school_object("DAY_OF_WEEK", menu_data, context)
    if error_message:
        return None, error_message

    keyboard = []
    for index, week_day in enumerate(day_of_week_list):
        button = [InlineKeyboardButton(week_day, callback_data=MenuData(menu_data.department, menu_data.class_, menu_data.week, index).to_string("DAY_OF_WEEK"))]
        keyboard.append(button)
    keyboard.append([InlineKeyboardButton("<<Назад", callback_data=MenuData(menu_data.department, menu_data.class_, -1).to_string("DAY_OF_WEEK"))])
    return InlineKeyboardMarkup(keyboard), None

def keyboard_button_week(menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> InlineKeyboardMarkup:
    """
    Получение списка недель месяца для MenuData
    """
    week_list: list
    week_list, error_message = get_school_object("WEEK", menu_data, context)
    if error_message:
        return None, error_message

    if len(week_list) == 1:
        return keyboard_button_day_of_week(MenuData(menu_data.department, menu_data.class_, 1), context)
    elif len(week_list) > 1:
        keyboard = []
        for week in week_list:
            button = [InlineKeyboardButton(f"Неделя месяца {week}", callback_data=MenuData(menu_data.department, menu_data.class_, week).to_string("WEEK"))]
            keyboard.append(button)
        keyboard.append([InlineKeyboardButton("<<Назад", callback_data=MenuData(menu_data.department, -1).to_string("WEEK"))])
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
    menu_data: MenuData = MenuData.from_string("CLASS", query.data)
    if menu_data.department == -1:
        # Нажата кнопка возврата
        reply_markup, error_message = keyboard_button_departments(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text(text="Выберете корпус:", reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Запросить список недель месяца
        reply_markup, error_message = keyboard_button_week(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text("Выберете неделю месяца", reply_markup=reply_markup)
        return START_ROUTES

async def week_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора недели месяца
    """
    logging.info("command week")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string("WEEK", query.data)
    if menu_data.class_ == -1:
        # Нажата кнопка возврата
        reply_markup, error_message = keyboard_button_classes(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text("Выберете класс", reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Запросить дни недели расписания
        reply_markup, error_message = keyboard_button_day_of_week(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text("Выберете день", reply_markup=reply_markup)
        return START_ROUTES
    return START_ROUTES

async def day_of_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Нажата кнопка выбора дня недели месяца
    """
    logging.info("command day of week")
    query = update.callback_query
    await query.answer()
    menu_data: MenuData = MenuData.from_string("DAY_OF_WEEK", query.data)
    if menu_data.week == -1:
        # Нажата кнопка возврата
        reply_markup, error_message = keyboard_button_classes(menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        await query.edit_message_text("Выберете класс", reply_markup=reply_markup)
        return START_ROUTES
    else:
        # Отобразить расписание
        lessons: Lesson
        lessons, error_message = get_school_object("LESSONS", menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        week_schedule: WeekSchedule
        week_schedule, error_message = get_school_object("WEEK_SCHEDULE", menu_data, context)
        if error_message:
            await query.edit_message_text(error_message)
            return START_ROUTES
        message = f"Расписание для класса {week_schedule.school_class.name}/{week_schedule.school_class.department.name}\n{week_schedule.school_class.link}\n"
        day_of_week_list = week_schedule.day_of_week_list(menu_data.week)
        message = f"{message}\n{day_of_week_list[menu_data.day_of_week]}:\n"
        lesson: Lesson
        for lesson in lessons:
            lesson_string = lesson.to_str(parse_mode = ParseMode.HTML)
            message += f"{lesson_string}\n"
        await query.edit_message_text(message, parse_mode=ParseMode.HTML)
        return START_ROUTES

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
    application = Application.builder().token(cfg.BOT_TOKEN).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, send_message))
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            START_ROUTES: [
                CallbackQueryHandler(school_button, pattern="^SCHOOL"),
                CallbackQueryHandler(department_button, pattern="^DEPARTMENT*"),
                CallbackQueryHandler(class_button, pattern="^CLASS*"),
                CallbackQueryHandler(week_button, pattern="^WEEK*"),
                CallbackQueryHandler(day_of_week, pattern="DAY_OF_WEEK*")
            ]
        },
        fallbacks=[CommandHandler("start", start)],
    )
    application.add_handler(conv_handler)

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
