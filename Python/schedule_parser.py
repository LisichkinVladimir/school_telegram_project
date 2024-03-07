"""
Модуль разбора учебного расписания
"""
import sys
import re
import logging
from hashlib import md5
import random
import requests
from bs4 import BeautifulSoup
import config as cfg
from week_pdf_parser import WeekSchedule, Lesson
from cache_func import timed_lru_cache, hash_string_to_byte
from database import save_to_db, load_from_db

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
        if link is None or cfg.BASE_URL in link:
            self.__link: str = link
        else:
            self.__link: str = cfg.BASE_URL + "/" + link
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
            self.__week_schedule = WeekSchedule(self)
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

    def get_class_by_id(self, class_id: int) -> SchoolClass:
        """ Получить класс по идентификатору"""
        class_: SchoolClass
        for class_ in self.__classes:
            if class_.id == class_id:
                return class_
        return None

    def __hash__(self) -> int:
        """ Вычисление хеша """
        return hash_string_to_byte(self.__name)

class School:
    """
    Класс школа
    """
    def __init__(self, url: str):
        """
        Конструктор класса
        """
        # Название школы
        self.__name: str = None
        # url страницы школы
        self.__url: str = url
        # список корпусов
        self.__departments: list = []
        # хэш последнего разбора расписания
        self.__hash: str = ""
        # идентификатор
        self.__id: int = None
        # Название текущего расписания
        self.__schedule_name: str = None

    def get_hash(self, response: requests.models.Response) -> str:
        """
        Получение хэша страницы
        """
        data = response.text
        # Уберем уникальные строки для подсчета хэша
        data_for_hash = re.sub(pattern = r"<link rel=\"stylesheet\" href=\"/css/app-project/app\.css.*/>", repl = "", string = data)
        data_for_hash = re.sub(pattern = r"<script defer src=\"/js/app-project/app.*</script>", repl = "", string = data_for_hash)
        data_for_hash = re.sub(pattern = r"<script async src=\"/js/app-project/build.*</script>", repl = "", string = data_for_hash)
        data_for_hash = re.sub(pattern = r"<script type=\"text/javascript\" src=\"/js/jquery.functions.js\?v=.*></script>", repl = "", string = data_for_hash)
        data_for_hash = data_for_hash.encode('utf-8', errors='ignore')
        return md5(data_for_hash).hexdigest()

    @timed_lru_cache(60*60*24)
    def load(self) -> bool:
        """
        Процедура загрузки данных о школе/расписании/корпусах
        """
        new_hash = None
        try:
            timeouts = (5, 10) # (conn_timeout, read_timeout)
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36 OPR/43.0.2442.991"
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/604.4.7 (KHTML, like Gecko) Version/11.0.2 Safari/604.4.7"
            ]
            headers = {"User-Agent": random.choice(user_agents)}
            logging.info(f"Get from {self.__url}. Use agent {headers}")
            response: requests.models.Response = requests.get(self.__url, timeout = timeouts, headers=headers)
            if response.status_code != 200:
                logging.error(f"Error get {self.__url}. error code {response.status_code}")
                return False
            logging.info(f"get {response.text[:25]}...\n")
            new_hash = self.get_hash(response)
            logging.info(f"hash {new_hash}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error {type(e)} {e}.\nTry get data from database")

        if self.__hash == new_hash and new_hash is not None:
            # разбор не нужен - хэш совпадает - значит данные не изменились
            logging.info("Hash not changed - used saved data")
            return True

        result = load_from_db(self, new_hash)
        if not result and new_hash is not None:
            # Данных в базе данных нет - разбираем данные страницы
            result = self.load_from_url(new_hash, response)
            if result:
                # записываем созданные объекты в базу
                save_to_db(self)
            return result

    def load_from_url(self, new_hash: str, response: requests.models.Response) -> bool:
        """
        Процедура разбора url расписания
        """
        # Получение html из Web
        data = response.text
        self.__hash = new_hash
        self.__departments = []
        self.__name = None
        self.__schedule_name: str = None
        self.__id = None

        xml_data = BeautifulSoup(data, 'lxml')
        # Получение названия школы
        if xml_data.find("title"):
            self.__name = xml_data.find("title").text
            position = self.__name.find("ГБОУ")
            if position > 0:
                self.__name = self.__name[position:]
                self.__id = hash_string_to_byte(self.__name)
        if self.__name is None:
            self.__id = hash_string_to_byte(self.__url)
        # Получение текущего расписания
        text_center = xml_data.find(['p'], attrs = {"style": "text-align: center;"})
        if text_center:
            schedule_name = text_center.text
            self.__schedule_name = schedule_name.strip().replace('\xa0', ' ').replace('\r\n', ' ')
        # Разбор HTML по территориям
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
    def name(self) -> str:
        """ Свойство возвращающее название школы """
        return self.__name

    @name.setter
    def name(self, value: str):
        """ Запись свойства название школы """
        self.__name = value

    @property
    def schedule_name(self) -> str:
        """ Свойство возвращающее название текущего расписания """
        return self.__schedule_name

    @schedule_name.setter
    def schedule_name(self, value: str):
        """ Запись свойства названия текущего расписания """
        self.__schedule_name = value

    @property
    def id(self) -> int:
        """ Свойство возвращающее идентификатор школы """
        return self.__id

    @id.setter
    def id(self, value: str):
        """ Запись свойства идентификатор школы """
        self.__id = value

    @property
    def departments(self, has_classes: bool = True) -> list:
        """ Свойство возвращающее список территорий """
        if has_classes:
            departments_list = []
            department: Department
            for department in self.__departments:
                if len(department.class_list) > 0:
                    departments_list.append(department)
            return departments_list
        else:
            return self.__departments

    def add_department(self, department: Department) -> None:
        """
        Добавляет подразделение
        """
        self.__departments.append(department)

    def get_department_by_id(self, department_id: int) -> Department:
        """ Поиск территории по идентификатору """
        department: Department
        for department in self.__departments:
            if department.id == department_id:
                return department
        return None

    def get_class_by_id(self, class_id: int) -> SchoolClass:
        """ Поиск класса по идентификатору """
        department: Department
        for department in self.__departments:
            class_: SchoolClass
            for class_ in department.class_list:
                if class_.id == class_id:
                    return class_
        return None

    @property
    def hash(self) -> str:
        """ Свойство возвращающее hash расписания """
        return self.__hash

    @hash.setter
    def hash(self, value: str):
        """ Запись свойства hash """
        self.__hash = value

    @property
    def url(self) -> str:
        """ Свойство url страницы школы """
        return self.__url

def main():
    """
    Разбора учебного расписания
    """
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    cfg.disable_logger(["httpcore.connection", "httpcore.http11"])
    cfg.disable_logger(["pdfminer.psparser", "pdfminer.pdfparser", "pdfminer.pdfinterp", "pdfminer.cmapdb", "pdfminer.pdfdocument", "pdfminer.pdfpage"])
    school: School = School(cfg.SCHEDULE_URL)
    school.load()
    print("----------------------------------------------")
    id_dict = {}
    error_list = []
    id_dict[school.id] = 1
    department: Department
    for department in school.departments:
        department_id = department.id
        if department_id in id_dict:
            id_dict[department_id] += 1
        else:
            id_dict[department_id] = 1
        print(f"{department.name} {department_id}")
        class_: SchoolClass
        for class_ in department.class_list:
            class_id = class_.id
            if class_id in id_dict:
                id_dict[class_id] += 1
            else:
                id_dict[class_id] = 1
            print(f"{class_.name}/[{class_id}];", end="")
            week_schedule: WeekSchedule = class_.week_schedule
            if not week_schedule.last_parse_result:
                print(f"!!!!!!!! Ошибка разбора {class_.link} - {week_schedule.last_parse_error}")
                error_list.append(f"!!!!!!!! Ошибка разбора {class_.link} - {week_schedule.last_parse_error}")
            else:
                for week in week_schedule.week_list():
                    for day_of_week in week_schedule.day_of_week_list(week):
                        print(f"week-{week} day_of_week-{day_of_week}")
                        lesson: Lesson
                        for lesson in week_schedule.lesson_list(week, day_of_week):
                            lesson_id = lesson.id
                            if lesson_id in id_dict:
                                id_dict[lesson_id] += 1
                            else:
                                id_dict[lesson_id] = 1
                            lesson_string = "[" + str(lesson_id) + "]" + lesson.to_str()
                            print(lesson_string)
        print("\n")
    print("------------------duplicate--------------------------")
    for key, value in id_dict.items():
        if value > 1:
            print(f"duplicate id {key}")
    print("-----------------error parse--------------------------")
    for error in error_list:
        print(error)

if __name__ == "__main__":
    main()
