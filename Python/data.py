"""
Модуль данных сессии бота
"""
import logging
from telegram.ext import ContextTypes
from schedule_parser import Schedules, Schedule, SchoolClass
from week_pdf_parser import WeekSchedule
import config as cfg

class BotData:
    """
    Данные сессии бота
    """
    def __init__(self):
        """
        Конструктор класса
        """
        self.__schedules: Schedules = None

    @property
    def schedules(self) -> Schedules:
        """ Свойство возвращающее расписания """
        if self.__schedules is None:
            self.__schedules = Schedules()
            # TODO сделать хранение и получение данных в SqLite
            self.__schedules.parse(cfg.SCHEDULE_URL)
        return self.__schedules

def create_schedules(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Создать расписание
    """
    if context.bot_data is not None:
        if "BotData" not in context.bot_data:
            logging.info("Create BotData for bot_data")
            bot_data = BotData()
            context.bot_data["BotData"] = bot_data
    elif context.user_data is not None:
        if "BotData" not in context.user_data:
            logging.info("Create BotData for bot_data")
            bot_data = BotData()
            context.user_data["BotData"] = bot_data

def get_schedules(context: ContextTypes.DEFAULT_TYPE) -> Schedules:
    """
    Получить расписания
    """
    create_schedules(context)
    if context.bot_data is not None and "BotData" in context.bot_data:
        logging.info("Get schedules from bot_data")
        return context.bot_data["BotData"].schedules
    elif context.user_data is not None and "BotData" in context.user_data:
        logging.info("Get schedules from user_data")
        return context.user_data["BotData"].schedules
    else:
        logging.info("Context bot_data and user_data is none")
        return BotData().schedules

class MenuData:
    """
    Данные передаваемые между меню
    """
    item_delimiter: str = ';'
    value_delimiter: str = '='

    def __init__(self, department: int = -1, class_: int = None, week: int = None, day_of_week: int = None):
        """
        Конструктор класса
        """
        self.dep_ind: int = department
        self.cls_ind: int = class_
        self.week_ind: int = week
        self.dow_ind: int = day_of_week

    def to_string(self, prefix: str) -> str:
        """
        Сериализация в строку
        """
        msg = prefix
        for key, value in self.__dict__.items():
            msg += key + self.value_delimiter + str(value) + self.item_delimiter
        return msg

    @classmethod
    def from_string(cls, prefix: str, s: str):
        """
        Де сериализация из строки
        """
        result = MenuData()
        s = s[len(prefix):]
        values = s.split(cls.item_delimiter)
        for val in values:
            if val:
                index = val.index(cls.value_delimiter)
                key = val[0:index]
                value = val[index+1:]
                if value == 'None':
                    result.__dict__[key] = None
                else:
                    result.__dict__[key] = int(value)
        return result

def get_schedule_object(class_name: str, menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> any:
    """
    Получить объект типа class_name
    """
    schedules: Schedules = get_schedules(context)
    if schedules is None:
        return None, "Список корпусов не определен"
    if class_name == "DEPARTMENT":
        return schedules, None

    department_index = menu_data.dep_ind
    if department_index < 0 or department_index > len(schedules.list)-1:
        return None, "Индекс корпуса не корректен"
    if class_name == "CLASS":
        return schedules.list[department_index], None

    class_index = menu_data.cls_ind
    schedule: Schedule = schedules.list[department_index]
    if class_index < 0 or class_index > len(schedule.class_list)-1:
        return None, "Индекс класса не корректен"

    school_class: SchoolClass = schedule.class_list[class_index]
    # Разбор pdf файла недельного расписания
    week_schedule: WeekSchedule = school_class.week_schedule
    if week_schedule is None:
        return None, "Список недель не определен"
    if class_name == "WEEK_SCHEDULE":
        return week_schedule, None
    week_list = week_schedule.week_list()
    if class_name == "WEEK":
        return week_list, None

    week_index = menu_data.week_ind
    if week_index < 0 or week_index > len(week_list)-1:
        return None, "Индекс недели не корректен"
    day_of_week_list = week_schedule.day_of_week_list(week_index + 1)
    if day_of_week_list is None:
        return None, "Список дней недели не определен"
    if class_name == "DAY_OF_WEEK":
        return day_of_week_list, None

    day_of_week_index = menu_data.dow_ind
    if day_of_week_index < 0 or day_of_week_index > len(day_of_week_list)-1:
        return None, "Индекс дня недели не корректен"
    day_of_week = day_of_week_list[day_of_week_index]
    if class_name == "LESSONS":
        return week_schedule.lesson_list(week_index + 1, day_of_week), None

    return None, "Не известный тип объекта"

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
