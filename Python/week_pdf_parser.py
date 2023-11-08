"""
Модуль разбора недельного pdf расписания
"""
from datetime import datetime

class Lesson:
    """
    Урок
    """
    def __init__(self, hour: int, week: int, name: str, office: str, group: str, teacher: str):
        """
        Конструктор класса
        hour: час начала урока
        week: чередование по неделям 
        name: название урока
        office: номер кабинета
        group: разделение классы на группы
        teacher: учитель
        """
        self.__hour: int = hour
        self.__week: int = week
        self.__name: str = name
        self.__office: str = office
        self.__group: str = group
        self.__teacher: str = teacher

class WeekSchedule:
    """
    Расписание класса на неделю/две недели
    """
    def __init__(self, class_name: str, department: str, url: str, created: str):
        """
        Конструктор класса
        class_name: название класса
        department: корпус
        url: url pdf файла
        created: str: дата создания
        """
        self.__class_name: str = class_name
        self.__department: str = department
        self.__url: str = url
        self.__created = datetime.strptime(created, "%d.%m.%Y")
        self.day_dict = {}