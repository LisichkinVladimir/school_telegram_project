"""
Модуль разбора учебного расписания
"""
import sys
import re
import logging
from hashlib import md5
import requests
from bs4 import BeautifulSoup
import config as cfg
from week_pdf_parser import WeekSchedule
from cache_func import timed_lru_cache, hash_string_to_byte

class SchoolClass:
    """
    Школьный класс
    """
    def __init__(self, name: str, link: str, department):
        """
        Конструктор класса
        name: название класса
        link: ссылка на pdf файл, содержащий расписание
        """
        # название класса
        self.__name: str = name
        match = re.search(R"^\d{1,2}", name)
        # номер класса
        self.__number: int = None
        if match and name[:match.end()].isnumeric():
            self.__number = int(name[:match.end()])
        # url с расписанием класса на неделю
        self.__link: str = link
        # корпус
        self.__department = department
        # расписание на неделю
        self.__week_schedule: WeekSchedule = None
        # идентификатор
        self.__id = hash(self)

    @property
    def name(self) -> str:
        """ Свойство name - название класса """
        return self.__name

    @property
    def number(self) -> int:
        """ Свойство number - номер класса """
        return self.__number

    @property
    def link(self) -> str:
        """ Свойство link - url с расписанием класса """
        return self.__link

    @property
    def week_schedule(self) -> WeekSchedule:
        """" Свойство расписание на неделю """
        if self.__week_schedule is None:
            self.__week_schedule = WeekSchedule(cfg.BASE_URL + "/" + self.__link)
        self.__week_schedule.parse()
        return self.__week_schedule

    @property
    def department(self):
        """ корпус класса """
        return self.__department

    @property
    def id(self) -> int:
        """ уникальный идентификатор """
        return self.__id

    def __hash__(self) -> int:
        """ Вычисление хеша """
        return hash_string_to_byte(self.__name + self.__department.name)

class Department:
    """
    Класс подразделение (корпус) школы
    """
    def __init__(self, name: str):
        """
        Конструктор класса
        name: название территории расписания
        """
        # название
        self.__name: str = name
        # список классов
        self.__classes: list = []
        # идентификатор
        self.__id = hash(self)

    def add_class(self, class_: SchoolClass):
        """ Метод добавление класса к списку классов """
        self.__classes.append(class_)

    @property
    def name(self) -> str:
        """ Свойство возвращающее название территории """
        return self.__name

    @property
    def class_list(self) -> list:
        """ Свойство возвращающее список классов территории """
        return self.__classes

    @property
    def id(self) -> int:
        """ уникальный идентификатор """
        return self.__id

    def __hash__(self) -> int:
        """ Вычисление хеша """
        return hash_string_to_byte(self.__name)

class Schedule:
    """
    Класс расписание
    """
    def __init__(self):
        """
        Конструктор класса
        """
        # список корпусов
        self.__departments: list = []
        # хэш последнего разбора расписания
        self.__hash: str  = ""

    @timed_lru_cache(60*60*24)
    def parse(self, url: str) -> bool:
        """
        Процедура разбора url расписания
        """
        # Получение html из Web
        response = requests.get(url)
        if response.status_code != 200:
            logging.error(f"Error get {url}. error code {response.status_code}")
            return False
        data = response.text
        logging.info(f"get {data[:25]}...\n")

        # Уберем уникальные строки для подсчета хэша
        data_for_hash = re.sub(pattern = r"<link rel=\"stylesheet\" href=\"/css/app-project/app\.css.*/>", repl = "", string = data)
        data_for_hash = re.sub(pattern = r"<script defer src=\"/js/app-project/app.*</script>", repl = "", string = data_for_hash)
        data_for_hash = re.sub(pattern = r"<script async src=\"/js/app-project/build.*</script>", repl = "", string = data_for_hash)
        data_for_hash = data_for_hash.encode('utf-8', errors='ignore')
        new_hash = md5(data_for_hash).hexdigest()
        logging.info(f"hash {new_hash}")
        if self.__hash == new_hash:
            return
        self.__hash = new_hash
        self.__departments = []

        # Разбор XML по территориям
        xml_data = BeautifulSoup(data, 'lxml')
        h3_list = xml_data.find_all(
                ['h3'],
                attrs = {"class": "toggle-heading", "style": "text-align: center;"}
                #string='span style'
        )

        # Цикл по территориям
        for h3 in h3_list:
            if '<h3 class="toggle-heading" style="text-align: center;"><span style="font-size' in str(h3):
                logging.info(f"Department {h3.text}....")
                department = Department(h3.text)

                # Поиск таблицы с расписаниями классов
                for sibling in h3.next_siblings:
                    table = sibling.find('table')
                    if table != -1:
                        table_body = table.find('tbody')
                        rows = table_body.find_all('tr')

                        for row in rows:
                            cols = row.find_all('td')
                            for col in cols:
                                # Разбор данных о классе
                                if col.text and col.text != '\xa0':
                                    url = None if col.a is None else col.a.get('href')
                                    logging.info(f"Class {col.text} {url}")
                                    class_ = SchoolClass(col.text, url, department)
                                    if class_.number is not None or url is not None:
                                        department.add_class(class_)

                self.__departments.append(department)
        return len(self.__departments) > 0

    @property
    def departments(self, has_classes: bool = True) -> list:
        """ Свойство возвращающее список территорий """
        if has_classes:
            departments_list = []
            for department in self.__departments:
                if len(department.class_list) > 0:
                    departments_list.append(department)
            return departments_list
        else:
            return self.__departments

    def hash(self) -> str:
        """ Свойство возвращающее hash расписания """
        return self.__hash

def main():
    """
    Разбора учебного расписания
    """
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    cfg.disable_logger(["httpcore.connection", "httpcore.http11"])
    cfg.disable_logger(["pdfminer.psparser", "pdfminer.pdfparser", "pdfminer.pdfinterp", "pdfminer.cmapdb", "pdfminer.pdfdocument", "pdfminer.pdfpage"])
    schedule = Schedule()
    schedule.parse(cfg.SCHEDULE_URL)
    print("----------------------------------------------")
    id_dict = {}
    error_list = []
    for department in schedule.departments:
        department_id = department.id
        if department_id in id_dict:
            id_dict[department_id] = id_dict[department_id] + 1
        else:
            id_dict[department_id] = 1
        print(f"{department.name} {department_id}")
        for class_ in department.class_list:
            week_schedule: WeekSchedule = class_.week_schedule
            if not week_schedule.last_parse_result:
                print(f"!!!!!!!! Ошибка разбора {week_schedule.url} - {week_schedule.last_parse_error}")
                error_list.append(f"!!!!!!!! Ошибка разбора {week_schedule.url} - {week_schedule.last_parse_error}")
            class_id = class_.id
            if class_id in id_dict:
                id_dict[class_id] = id_dict[class_id] + 1
            else:
                id_dict[class_id] = 1
            print(f"{class_.name}/[{class_id}];", end="")
        print("\n")
    print("----------------------------------------------")
    for key, value in id_dict.items():
        if value > 1:
            print(f"duplicate id {key}")
    for error in error_list:
        print(error)

if __name__ == "__main__":
    main()
