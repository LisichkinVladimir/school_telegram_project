"""
Модуль данных сессии бота
"""
import logging
from datetime import datetime
from telegram.ext import ContextTypes
from schedule_parser import School, Department, SchoolClass
from week_pdf_parser import WeekSchedule
import config as cfg

DEPARTMENT_OBJECT = "DEPARTMENT"
CLASS_OBJECT = "CLASS"
WEEK_SCHEDULE_OBJECT = "WEEK_SCHEDULE"
WEEK_OBJECT = "WEEK"
DAY_OF_WEEK_OBJECT = "DAY_OF_WEEK"
LESSONS_OBJECT = "LESSONS"

class BotData:
    """
    Данные сессии бота
    """
    def __init__(self):
        """
        Конструктор класса
        """
        self.__school: School = None

    @property
    def school(self) -> School:
        """ Свойство возвращающее объект школа """
        if self.__school is None:
            self.__school = School(cfg.SCHEDULE_URL)
        self.__school.load()
        return self.__school

class UserData:
    """
    Данные сессии пользователя
    """
    def __init__(self):
        """
        Конструктор класса
        """
        self.last_class_name: str = None
        self.last_datetime = None
        self.user_id: int = None
        self.seconds: int = None

    def __str__(self) -> str:
        """ 
        Преобразование в строку
        """
        last_datetime = ""
        if self.last_datetime is not None:
            last_datetime = self.last_datetime.strftime("%d/%m/%y %H:%M")
        else:
            last_datetime = None
        return f"user_id={self.user_id} last_class_name={self.last_class_name} last_datetime={last_datetime} seconds={self.seconds}"

class IntervalError(Exception):
    """ Класс ошибки когда между запросами минимальный интервал"""
    def __init__(self, message):
        pass

def create_context_data(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
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
    if context.user_data is not None:
        if "UserData" not in context.user_data:
            logging.info("Create UserData")
            user_data = UserData()
            user_data.user_id = user_id
            context.user_data["UserData"] = user_data

def get_school(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> School:
    """
    Получить данные школы
    """
    create_context_data(context, user_id)
    if context.bot_data is not None and "BotData" in context.bot_data:
        logging.info("Get school from bot_data")
        return context.bot_data["BotData"].school
    elif context.user_data is not None and "BotData" in context.user_data:
        logging.info("Get school from user_data")
        return context.user_data["BotData"].school
    else:
        logging.info("Context bot_data and user_data is none")
        return BotData().school

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

def get_school_object(class_name: str, menu_data: MenuData, context: ContextTypes.DEFAULT_TYPE) -> any:
    """
    Получить объект типа class_name
    """
    school: School = get_school(context, None)
    if school is None:
        return None, "Расписание не загружено"
    if context.user_data is not None and "UserData" in context.user_data:
        user_data: UserData = context.user_data["UserData"]
        if user_data.last_class_name is None:
            user_data.last_class_name = class_name
            user_data.last_datetime = datetime.now()
        elif user_data.last_class_name == class_name and user_data.last_datetime is not None:
            time_now = datetime.now()
            time_diff = time_now - user_data.last_datetime
            user_data.seconds = time_diff.total_seconds()
            logging.debug(f"Same class_name. Time diff {user_data.seconds}")
            logging.debug(f"Last usage {user_data.last_datetime.strftime('%d/%m/%y %H:%M')}")
            logging.debug(f"New usage {time_now.strftime('%d/%m/%y %H:%M')}")
            if user_data.seconds < 2:
                logging.warning("Interval is too small")
                raise IntervalError("Interval is too small")
            else:
                user_data.last_datetime = datetime.now()
        else:
            user_data.last_datetime = datetime.now()
            user_data.last_class_name = class_name
            user_data.seconds = None
        context.user_data["UserData"] = user_data

    if class_name == DEPARTMENT_OBJECT:
        return school, None

    department_id = menu_data.department
    department: Department = school.get_department_by_id(department_id)
    if department is None:
        return None, "Идентификатор корпуса не корректен"
    if class_name == CLASS_OBJECT:
        return department, None

    class_id = menu_data.class_
    school_class: SchoolClass = department.get_class_by_id(class_id)
    if school_class is None:
        return None, "Идентификатор класса не корректен"

    # Разбор pdf файла недельного расписания
    week_schedule: WeekSchedule = school_class.week_schedule
    if week_schedule is None:
        return None, "Список недель не определен"
    if not week_schedule.last_parse_result:
        return None, f"{week_schedule.last_parse_error}\n{school_class.link}"
    if class_name == WEEK_SCHEDULE_OBJECT:
        return week_schedule, None
    week_list = week_schedule.week_list()
    if class_name == WEEK_OBJECT:
        return week_list, None

    day_of_week_list = week_schedule.day_of_week_list(menu_data.week)
    if day_of_week_list is None:
        return None, "Список дней недели не определен"
    if class_name == DAY_OF_WEEK_OBJECT:
        return day_of_week_list, None

    day_of_week_index = menu_data.day_of_week
    if day_of_week_index < 0 or day_of_week_index > len(day_of_week_list)-1:
        return None, "Индекс дня недели не корректен"
    day_of_week = day_of_week_list[day_of_week_index]
    if class_name == LESSONS_OBJECT:
        return week_schedule.lesson_list(menu_data.week, day_of_week), None

    return None, "Не известный тип объекта"

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
