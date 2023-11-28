"""
Модуль данных сессии бота
"""
import logging
from telegram.ext import ContextTypes
from schedule_parser import Schedule, Department, SchoolClass
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
        self.__schedule: Schedule = None

    @property
    def schedule(self) -> Schedule:
        """ Свойство возвращающее расписание """
        if self.__schedule is None:
            self.__schedule = Schedule()
        self.__schedule.parse(cfg.SCHEDULE_URL)
        return self.__schedule

def create_schedule(context: ContextTypes.DEFAULT_TYPE) -> None:
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

def get_schedule(context: ContextTypes.DEFAULT_TYPE) -> Schedule:
    """
    Получить расписания
    """
    create_schedule(context)
    if context.bot_data is not None and "BotData" in context.bot_data:
        logging.info("Get schedule from bot_data")
        return context.bot_data["BotData"].schedule
    elif context.user_data is not None and "BotData" in context.user_data:
        logging.info("Get schedule from user_data")
        return context.user_data["BotData"].schedule
    else:
        logging.info("Context bot_data and user_data is none")
        return BotData().schedule

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
        self.dp_i: int = department
        self.c_i: int = class_
        self.w_i: int = week
        self.dw_i: int = day_of_week

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

    @property
    def department(self) -> int:
        """ Корпус """
        return self.dp_i

    @property
    def class_(self) -> int:
        """ Класс """
        return self.c_i

    @property
    def week(self) -> int:
        """ Чередование по неделям"""
        return self.w_i

    @property
    def day_of_week(self) -> int:
        """ День недели """
        return self.dw_i

def get_schedule_object(class_name: str, menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> any:
    """
    Получить объект типа class_name
    """
    schedule: Schedule = get_schedule(context)
    if schedule is None:
        return None, "Расписание не загружено"
    if class_name == "DEPARTMENT":
        return schedule, None

    department_index = menu_data.department
    if department_index < 0 or department_index > len(schedule.departments)-1:
        return None, "Индекс корпуса не корректен"
    if class_name == "CLASS":
        return schedule.departments[department_index], None

    class_index = menu_data.class_
    department: Department = schedule.departments[department_index]
    if class_index < 0 or class_index > len(department.class_list)-1:
        return None, "Индекс класса не корректен"

    school_class: SchoolClass = department.class_list[class_index]
    # Разбор pdf файла недельного расписания
    week_schedule: WeekSchedule = school_class.week_schedule
    if week_schedule is None:
        return None, "Список недель не определен"
    if not week_schedule.last_parse_result:
        return None, f"{week_schedule.last_parse_error}\n{week_schedule.url}"
    if class_name == "WEEK_SCHEDULE":
        return week_schedule, None
    week_list = week_schedule.week_list()
    if class_name == "WEEK":
        return week_list, None

    week_index = menu_data.week
    if week_index < 0 or week_index > len(week_list)-1:
        return None, "Индекс недели не корректен"
    day_of_week_list = week_schedule.day_of_week_list(week_index + 1)
    if day_of_week_list is None:
        return None, "Список дней недели не определен"
    if class_name == "DAY_OF_WEEK":
        return day_of_week_list, None

    day_of_week_index = menu_data.day_of_week
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
