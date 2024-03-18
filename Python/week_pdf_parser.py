"""
Модуль разбора недельного pdf расписания
"""
import sys
import io
import logging
import re
from datetime import datetime
from hashlib import md5
from urllib.parse import unquote
import random
import requests
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTFigure
from telegram.constants import ParseMode
import pdfplumber
from cache_func import timed_lru_cache, hash_string
import config as cfg
from database import load_pdf_from_db, save_pdf_to_db

class LessonIdent:
    """
    Идентификатор урока
    """
    def __init__(self, week: int, hour_start: str, day_of_week: str, day_of_week_number: int):
        """
        Конструктор класса
        week: чередование по неделям
        hour: час начала урока
        day_of_week: день недели
        """
        self.__week: int = week
        self.__hour_start: str = hour_start
        self.__day_of_week: str = day_of_week
        self.__day_of_week_number: int = day_of_week_number
        # идентификатор
        self.__id = hash(self)

    def __hash__(self) -> int:
        """ Вычисление хеша """
        return hash_string(f"{self.__week}_{self.__hour_start}_{self.__day_of_week}")

    def __eq__(self, other) -> bool:
        """ Функция сравнения """
        return (self.__week == other.week) and (self.__hour_start == other.hour_start) and (self.__day_of_week == other.day_of_week)

    @property
    def week(self) -> int:
        """ Свойство чередование по неделям """
        return self.__week

    @property
    def hour_start(self) -> str:
        """ Свойство начало урока/номер урока """
        return self.__hour_start

    @property
    def day_of_week(self) -> str:
        """ Свойство день недели """
        return self.__day_of_week

    @property
    def day_of_week_number(self) -> int:
        """ Свойство номер дня недели """
        return self.__day_of_week_number

    @property
    def id(self) -> int:
        """ уникальный идентификатор """
        return self.__id

class Lesson:
    """
    Урок
    """
    PRINT_HOURS = 0
    PRINT_OFFICE = 2
    PRINT_GROUP = 4
    PRINT_TEACHER = 8
    PRINT_ALL: set = {PRINT_HOURS, PRINT_OFFICE, PRINT_GROUP, PRINT_TEACHER}

    def __init__(self, ident: LessonIdent, name: str, office: str, group: str, teacher: str, class_name: str, row_data: str):
        """
        Конструктор класса
        ident: идентификатор урока (неделя/день недели/час)
        name: название урока
        office: номер кабинета
        group: разделение классы на группы
        teacher: учитель
        """
        self.__ident: LessonIdent = ident
        self.__hour_end: str = ident.hour_start
        self.__name: str = name
        self.__office: str = office
        self.__group: str = group
        self.__teacher: str = teacher
        self.__class_name: str = class_name
        self.__row_data: str = row_data
        self.__groups: list = []
        self.__id: int = hash_string(f"{self.__name}_{self.ident.week}_{self.ident.hour_start}_{self.ident.day_of_week}_{self.__office}_{self.__group}_{self.__teacher}_{self.__class_name}")

    @property
    def ident(self) -> LessonIdent:
        """" Свойство идентификатор урока """
        return self.__ident

    @property
    def hour_end(self) -> str:
        """" Свойство Время окончания урока """
        return self.__hour_end

    @hour_end.setter
    def hour_end(self, value: int):
        self.__hour_end = value

    @property
    def name(self) -> str:
        """" Свойство название урока """
        return self.__name

    @property
    def office(self) -> str:
        """" Свойство кабинет """
        return self.__office

    @property
    def group(self) -> str:
        """" Свойство группа """
        return self.__group

    @property
    def teacher(self) -> str:
        """" Свойство преподаватель """
        return self.__teacher

    @property
    def class_name(self) -> str:
        """ Название класса """
        return self.__class_name

    @property
    def row_data(self) -> str:
        """" Сырые данные из ячейки pdf таблицы """
        return self.__row_data

    @property
    def groups(self) -> list:
        """" разбиение урока на группы """
        return self.__groups

    @property
    def id(self) -> int:
        """ уникальный идентификатор """
        return self.__id

    def to_str(self, what_to_print: set = PRINT_ALL, parse_mode = None) -> str:
        """ Конвертация урока в строку """
        # Начало урока
        if self.PRINT_HOURS in what_to_print:
            if self.ident.hour_start == self.hour_end:
                result = f"[{self.ident.hour_start}]"
            else:
                result = f"[{self.ident.hour_start}-{self.hour_end}]"
            if result and parse_mode == ParseMode.HTML:
                result = "<b>" + result + "</b>"
        else:
            result = ""
        # название урока
        if self.name:
            result = f"{result} {self.name}"
        # номер кабинета
        if self.PRINT_OFFICE in what_to_print and self.office:
            result = f"{result} каб.{self.office}"
        # номер группы
        if self.PRINT_GROUP in what_to_print and self.group:
            result = f"{result} гр. {self.group}"
        # преподаватель
        if self.PRINT_TEACHER in what_to_print and self.teacher:
            result = f"{result} {self.teacher}"
        if len(self.groups) > 0:
            group_item: Lesson
            for group_item in self.groups:
                result = f"{result} // {group_item.name}"
                if self.PRINT_OFFICE in what_to_print and group_item.office:
                    result = f"{result} каб.{group_item.office}"
                if self.PRINT_GROUP in what_to_print and group_item.group:
                    result = f"{result} гр. {group_item.group}"
                if self.PRINT_TEACHER in what_to_print and group_item.teacher:
                    result = f"{result} {group_item.teacher}"
        return result.strip()

class DayOfWeek:
    """
    Вспомогательный класс предназначенный для поиска строки или столбцов дней недели
    """
    week_names: dict = {
        0: ['ПН','ПОНЕДЕЛЬНИК'],
        1: ['ВТ', 'ВТОРНИК'],
        2: ['СР', 'СРЕДА'],
        3: ['ЧТ', 'ЧЕТВЕРГ'],
        4: ['ПТ', 'ПЯТНИЦА'],
        5: ['СБ', 'СУББОТА'],
        6: ['ВС', 'ВОСКРЕСЕНЬЕ']
    }

    def get_week_index(self, week_name: str)->int:
        """
        Получить индекс по названию дня недели
        """
        if week_name is None:
            return None
        week_name = week_name.upper()
        for index, week_names in self.week_names.items():
            for name in week_names:
                if name == week_name:
                    return index
        return None

    def __init__(self, tables: list):
        """
        Конструктор класса
        """
        # Словарь с найденными днями неделями
        self.__has_week: bool = False
        self.__row_index: int = -1
        self.__column_index: int = -1
        self.__week_name_indexes: dict = {}
        self.__week_number_indexes: dict = {}
        for table in tables:
            self.__has_week = False
            if len(table) > 0:
                # Получение индексов дней недели
                for i, row in enumerate(table):
                    for j, col in enumerate(row):
                        index = self.get_week_index(col)
                        if index is not None:
                            self.__week_name_indexes[col] = [i, j]
                            self.__week_number_indexes[index] = col
                            self.__has_week = True
                if self.__has_week:
                    logging.info(f"week_name_indexes={self.__week_name_indexes}, week_number_indexes={self.__week_number_indexes}")
                    # Определение - дни недели по строкам или столбцам
                    self.__row_index = next(iter(self.__week_name_indexes.values()))[0]
                    self.__column_index = next(iter(self.__week_name_indexes.values()))[1]
                    for value in self.__week_name_indexes.values():
                        if self.__row_index != value[0]:
                            self.__row_index = -1
                        if self.__column_index != value[1]:
                            self.__column_index = -1
        # Сортировка по номеру дня недели от Пн-Вс
        week_name_indexes = {}
        week_number_indexes = {}
        sorted_index = sorted(self.__week_number_indexes.items())
        for index in sorted_index:
            i = index[0]
            week_name = index[1]
            position = self.__week_name_indexes[week_name]
            week_name_indexes[week_name] = position
            week_number_indexes[index] = week_name

        self.__week_name_indexes = week_name_indexes
        self.__week_number_indexes = week_number_indexes

    def get_day_of_week_by_row(self, row_index: int) -> str:
        """
        Поиск дня недели по индексу столбца
        """
        for key, value in self.__week_name_indexes.items():
            if value[1] == row_index:
                return key
        return None

    def get_day_of_week_by_column(self, column_index) -> str:
        """
        Поиск дня недели по индексу строки
        """
        for key, value in self.__week_name_indexes.items():
            if value[0] == column_index:
                return key
        return None

    @property
    def has_week(self) -> bool:
        """ признак что дни недели найдены в таблице """
        return self.__has_week

    @property
    def row_index(self) -> int:
        """ Строка в которой содержатся дни недели """
        return self.__row_index

    @property
    def column_index(self) -> int:
        """ Столбец в котором содержатся дни недели """
        return self.__column_index

    @property
    def week_indexes(self) -> list:
        """ Индексы ячеек дней неделей """
        week_numbers = []
        for key in self.__week_number_indexes.keys():
            week_numbers.append(key)
        return week_numbers

    def get_first_column(self) -> int:
        """ Получить первый столбец дней недели """
        column = next(iter(self.__week_name_indexes.values()))[1]
        return column

    def get_first_row(self) -> int:
        """ Получить первую строку дней недели """
        row = next(iter(self.__week_name_indexes.values()))[0]
        return row

class WeekSchedule:
    """
    Расписание класса на неделю/две недели
    """
    def __init__(self, school_class = None):
        """
        Конструктор класса
        class_name: название класса
        department: корпус
        url: url pdf файла
        created: str: дата создания
        """
        self.__school_class = school_class
        self.__created = None
        self.__hash: str = ""
        self.__last_parse_result = False
        self.__last_parse_error = None
        self.__lesson_dict = {}

    def add_lesson(self, lesson_ident: LessonIdent, new_lesson: Lesson):
        """
        Добавить новый урок
        """
        if lesson_ident not in self.__lesson_dict:
            self.__lesson_dict[lesson_ident] = new_lesson
        else:
            # Разбиение урока на группы
            lesson: Lesson = self.__lesson_dict[lesson_ident]
            lesson.groups.append(new_lesson)

    def add_group_lesson(self, lesson_ident: LessonIdent, new_lesson: Lesson):
        """
        Добавить новый урок
        """
        lesson: Lesson = self.__lesson_dict[lesson_ident]
        lesson.groups.append(new_lesson)

    def __parse_office(self, lesson: str) -> tuple:
        """
        Разбираем кабинет в названии урока
        """
        office = None
        match = re.search(R"\d+\D{0,1}", lesson)
        if match:
            office = lesson[match.start():match.end()].strip()
            lesson = lesson.replace(office, "").strip()
            if office[-1] == ",":
                match = re.search(R"\d+", lesson)
                if match:
                    office2 = lesson[match.start():match.end()].strip()
                    lesson = lesson.replace(office2, "").strip()
                    office = office + office2

        return (office, lesson)

    def __parse_teacher(self, lesson)-> tuple:
        """
        разбор фамилии учителя"""
        teacher = None
        match = re.search(R"\s[а-яА-Я]+\s\D\.\D\.", lesson)
        if match:
            teacher = lesson[match.start():].strip()
            lesson = lesson.replace(teacher, "").strip()
        return(teacher, lesson)

    def __parse_lesson(self, lesson: str, week, hour, day_of_week: str, day_of_week_number: int, class_name: str = None) -> None:
        """
        Разобрать lesson - достать name/office/group
        """
        row_data = lesson
        lesson = lesson.replace("\n", " ")
        # group - поиск групп в названии
        group = None
        if self.__school_class is not None:
            class_name = self.__school_class.name
        if class_name is not None and class_name in lesson:
            s = class_name + R".\d{1}"
            match = re.search(RF"{s}", lesson)
            if match:
                group = lesson[match.start():match.end()]
                lesson = lesson.replace(group, "")
            else:
                s = class_name + R"\d{1}"
                match = re.search(RF"{s}", lesson)
                if match:
                    group = lesson[match.start():match.end()]
                    lesson = lesson.replace(group, "")
        else:
            if "1 группа" in lesson:
                group = "1 группа"
                lesson = lesson.replace("1 группа", "")
            elif "2 группа" in lesson:
                group = "2 группа"
                lesson = lesson.replace("2 группа", "")
        # office - поиск кабинета
        parse_office = self.__parse_office(lesson)
        office = parse_office[0]
        lesson = parse_office[1]
        # teacher - поиск учителя
        parse_teacher = self.__parse_teacher(lesson)
        teacher= parse_teacher[0]
        lesson = parse_teacher[1]
        name = lesson
        logging.info(f"day_of_week={day_of_week} lesson={name} group={group} office={office} teacher={teacher}")
        if name == "":
            return
        # Создание урока по найденным значениям
        lesson_ident: LessonIdent = LessonIdent(week, hour, day_of_week, day_of_week_number)
        new_lesson = Lesson(
            ident = lesson_ident,
            name = name,
            office = office,
            group = group,
            teacher = teacher,
            class_name = None if self.__school_class is None else self.__school_class.name,
            row_data = row_data)
        self.add_lesson(lesson_ident, new_lesson)

    def __parse_week_by_row(self, table: list, day_of_week: DayOfWeek, class_name: str = None) -> bool:
        """
        Разбор расписания где дни недели по строкам к строке day_of_week.row_index
        """
        first_column = day_of_week.get_first_column()
        hour_index = first_column - 1
        week_index = None
        if hour_index >= 1:
            week_index = hour_index - 1
        week = 1
        hour_counter = 1
        if hour_index == -1:
            first_column = day_of_week.row_index + 1
        # Цикл по часам i - столбец
        for i in range(first_column, len(table)):
            hour = None
            if hour_index >=0:
                # Поиск столбца с часами
                if table[i][hour_index] is not None and table[i][hour_index].isnumeric():
                    hour = int(table[i][hour_index])
                elif hour_index >= 1:
                    hour_index -= 1
                    if table[i][hour_index] is not None and table[i][hour_index].isnumeric():
                        hour = int(table[i][hour_index])
                        if hour_index >= 1:
                            week_index = hour_index - 1
                        else:
                            week_index = None
            else:
                # Столбца с часами нет - просто 1,2,....
                hour = hour_counter
                hour_counter += 1
            if hour is None:
                continue
            if week_index is not None and table[i][week_index] is not None and table[i][week_index].isnumeric():
                week = int(table[i][week_index])
            logging.info(f"week={week} hour={hour}")
            # Цикл по дням недели
            for j in range(hour_index + 1, len(table[i])):
                day = day_of_week.get_day_of_week_by_row(j)
                if day is None and hour_index != -1:
                    # Урок больше одного часа
                    day = day_of_week.get_day_of_week_by_row(j-1)
                if day:
                    lesson = table[i][j]
                    if lesson is not None and lesson != '':
                        # Есть урок
                        day_of_week_number = day_of_week.get_week_index(day)
                        self.__parse_lesson(lesson, week, hour, day, day_of_week_number, class_name)
                        self.__last_parse_result = True
                    elif i > 2 and table[i-1][j] and hour_index != -1:
                        # lesson is None но предыдущий столбец есть - проверяем это не второй час урока
                        prev_row_data = table[i-1][j]
                        day_of_week_number = day_of_week.get_week_index(day)
                        lesson_ident: LessonIdent = LessonIdent(week, hour-1, day, day_of_week_number)
                        if lesson_ident in self.__lesson_dict:
                            lesson: Lesson = self.__lesson_dict[lesson_ident]
                            if lesson.row_data == prev_row_data:
                                lesson.hour_end = hour
                            elif len(lesson.groups) > 0:
                                group: Lesson
                                for group in lesson.groups:
                                    if group.row_data == prev_row_data:
                                        group.hour_end = hour
        return self.__last_parse_result

    def __parse_week_by_column(self, table: list, day_of_week: DayOfWeek, class_name: str = None) -> bool:
        """
        Разбор расписания где дни недели по столбцам к столбце day_of_week.column_index
        """
        week = 1
        week_index = day_of_week.column_index - 1
        first_row = day_of_week.get_first_row()
        for i in range(first_row, len(table)):
            if week_index >= 0 and table[i][week_index] is not None and table[i][week_index].isnumeric():
                week = int(table[i][week_index])
            day = day_of_week.get_day_of_week_by_column(i)
            if day is None:
                # Урок разбит на две группы
                day = day_of_week.get_day_of_week_by_column(i-1)
            if day:
                logging.info(f"week={week} day of week={day}")
                for j in range(day_of_week.column_index + 1, len(table[i])):
                    lesson = table[i][j]
                    hour = table[first_row-1][j].replace("\n", " ")
                    if lesson is not None and lesson != '':
                        # Есть урок
                        day_of_week_number = day_of_week.get_week_index(day)
                        self.__parse_lesson(lesson, week, hour, day, day_of_week_number, class_name)
                        self.__last_parse_result = True
        return self.__last_parse_result

    @timed_lru_cache(60*60*24)
    def parse(self, url = None, use_db_cash: bool = True) -> bool:
        """
        Процедура разбора url расписания
        """
        # Получение html из Web
        if self.__school_class is not None:
            url = self.__school_class.link
        logging.info(f"get {url}")
        try:
            timeouts = (6, 20) # (conn_timeout, read_timeout)
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36 OPR/43.0.2442.991"
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_2) AppleWebKit/604.4.7 (KHTML, like Gecko) Version/11.0.2 Safari/604.4.7"
            ]
            headers = {"User-Agent": random.choice(user_agents)}
            logging.info(f"Get from {url}. Use agent {headers}")
            response = requests.get(url, timeout = timeouts, headers=headers)
            if response.status_code != 200:
                self.__last_parse_error = f"Error get {url}. error code {url}"
                logging.error(self.__last_parse_error)
                return False
        except requests.exceptions.RequestException as e:
            logging.error(f"Error {type(e)} {e}")
            return False

        # Вычисление хэша
        new_hash = md5(response.content).hexdigest()
        logging.info(f"hash {new_hash}")
        if self.__hash == new_hash and use_db_cash:
            self.__last_parse_error = "Hash not changed - used saved data"
            logging.info(self.__last_parse_error)
            return self.__last_parse_result

        if use_db_cash:
            self.__last_parse_result = load_pdf_from_db(self, new_hash)
            if self.__last_parse_result:
                self.__last_parse_error = "Lessons successful loaded from Db"
                logging.info(self.__last_parse_error)
        else:
            self.__last_parse_result = False
        if not self.__last_parse_result and new_hash is not None:
            # Данных в базе данных нет - разбираем данные страницы
            self.__last_parse_result = self.load_pdf_from_url(new_hash, url, response)
            if self.__last_parse_result:
                self.__last_parse_error = "Lessons successful loaded from url"
                # записываем созданные объекты в базу
                save_pdf_to_db(self)

        return self.__last_parse_result

    def load_pdf_from_url(self, new_hash: str, url: str, response: requests.models.Response) -> bool:
        """
        Процедура разбора pdf расписания
        """
        self.__hash = new_hash
        self.__lesson_dict = {}
        self.__created = None
        self.__last_parse_result = False
        self.__last_parse_error = None

        mem_obj = io.BytesIO(response.content)
        pdfReader = PdfReader(mem_obj)
        # printing number of pages in pdf file
        pages = len(pdfReader.pages)
        if pages == 0:
            self.__last_parse_error = "Ошибка разбора pdf. Нулевое количество страниц"
            logging.error(self.__last_parse_error)
            return False
        logging.info(f"Pdf pages {pages}")
        # extract page structure
        layouts = extract_pages(mem_obj)
        pages_num = 0
        element_num = 0
        if self.__school_class is not None:
            class_name = self.__school_class.name
        else:
            class_name = url[url.rfind('/') + 1:]
            class_name = unquote(class_name)
            class_name = class_name.replace(".pdf", "")
        for page_layout in layouts:
            if isinstance(page_layout, LTPage):
                pages_num += 1
                element_num = 0
            for element in page_layout:
                element_num += 1
                if isinstance(element, LTTextContainer):
                    s = element.get_text()
                    if s.find("Составлено:") >= 0:
                        match = re.search(R"\d{1,2}\.\d{1,2}\.\d{4}", s)
                        if match:
                            self.__created = datetime.strptime(s[match.start():match.end()], "%d.%m.%Y")
                elif isinstance(element, LTFigure):
                    self.__last_parse_error = "PDF содержит сканированное изображение - распознавание не возможно"
                    logging.warning(self.__last_parse_error)
        logging.info(f"class={class_name} created={self.__created}")

        # Разбор таблицы
        pdf = pdfplumber.open(mem_obj)
        for page_num in range(0, pages):
            table_page = pdf.pages[page_num]
            tables = table_page.extract_tables()
            for table in tables:
                if len(table) > 0:
                    # Получение индексов дней недели
                    day_of_wek: DayOfWeek = DayOfWeek(tables)
                    if day_of_wek.has_week:
                        if day_of_wek.row_index >= 0 and day_of_wek.column_index == -1:
                            logging.info(f"week indexes by row {day_of_wek.row_index}")
                            result = self.__parse_week_by_row(table, day_of_wek, class_name)
                            if result:
                                self.__last_parse_error = None
                            return result
                        elif day_of_wek.column_index >= 0 and day_of_wek.row_index == -1:
                            logging.info(f"week indexes by column {day_of_wek.column_index}")
                            result = self.__parse_week_by_column(table, day_of_wek, class_name)
                            if result:
                                self.__last_parse_error = None
                            return result
                    else:
                        self.__last_parse_error = "Не возможно найти в таблице дни недели"
                        logging.error(self.__last_parse_error)
                        return False
        return self.__last_parse_result

    def week_list(self) -> list:
        """
        Список чередования по неделям
        """
        result = []
        key: LessonIdent
        for key in self.__lesson_dict:
            if key.week not in result:
                result.append(key.week)
        return result

    def day_of_week_list(self, week: int) -> list:
        """
        Список учебных дней недели
        """
        day_list = {}
        key: LessonIdent
        for key in self.__lesson_dict:
            if key.week == week and key.day_of_week_number not in day_list:
                day_list[key.day_of_week_number] = key.day_of_week
        sorted_days = sorted(day_list.items())
        result = []
        for day in sorted_days:
            result.append(day[1])
        return result

    def lesson_list(self, week: int, day_of_week: str) -> list:
        """
        Список уроков дня
        """
        result = []
        key: LessonIdent
        for key, value in self.__lesson_dict.items():
            if key.week == week and key.day_of_week == day_of_week:
                result.append(value)
        result_sorted = sorted(result, key=lambda lesson: lesson.ident.hour_start)
        return result_sorted

    @property
    def hash(self) -> str:
        """ Свойство хэш pdf """
        return self.__hash

    @hash.setter
    def hash(self, value: str):
        """ Setter свойства хэш pdf """
        self.__hash = value

    @property
    def school_class(self):
        """ Свойство school_class """
        return self.__school_class

    @property
    def created(self):
        """ Свойство дата создания pdf """
        return self.__created

    @created.setter
    def created(self, value):
        """ Setter свойства дата создания pdf """
        self.__created = value

    @property
    def last_parse_result(self) -> bool:
        """ Был ли разбор успешен """
        return self.__last_parse_result

    @last_parse_result.setter
    def last_parse_result(self, value: bool):
        """ Setter Был ли разбор успешен """
        self.__last_parse_result = value

    @property
    def last_parse_error(self) -> str:
        """ Ошибка разбора """
        if self.__last_parse_error is None or self.__last_parse_error:
            return self.__last_parse_error
        else:
            return "Ошибка разбора pdf страницы"

    @last_parse_error.setter
    def last_parse_error(self, value: str):
        """ Setter Ошибка разбора """
        self.__last_parse_error = value

def main():
    """
    Разбора pdf расписания класса
    """
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    cfg.disable_logger(["pdfminer.psparser", "pdfminer.pdfparser", "pdfminer.pdfinterp", "pdfminer.cmapdb", "pdfminer.pdfdocument", "pdfminer.pdfpage"])
    #url = "https://1502.mskobr.ru//files/rasp/alpha/8Ж.pdf"
    #url = "https://1502.mskobr.ru/files/rasp/alpha/7%D0%95.pdf"
    #url = "https://1502.mskobr.ru//files/rasp/delta3/2%D0%BE.pdf"
    #url = "https://1502.mskobr.ru//files/rasp/beta/1А.pdf"
    #url = "https://1502.mskobr.ru//files/rasp/beta/1Б.pdf"
    #url = "https://1502.mskobr.ru//files/rasp/beta/2А.pdf"
    #url = 'https://1502.mskobr.ru//files/rasp/beta/2Б.pdf'
    #url = 'https://1502.mskobr.ru//files/rasp/gamma/7Л.pdf'
    url = "https://1502.mskobr.ru//files/rasp/delta1/5%D1%8E.pdf"
    week_schedule = WeekSchedule()
    week_schedule.parse(url, False)
    print("----------------------------------------------")
    for week in week_schedule.week_list():
        for day_of_week in week_schedule.day_of_week_list(week):
            print(f"week-{week} day_of_week-{day_of_week}")
            lesson: Lesson
            for lesson in week_schedule.lesson_list(week, day_of_week):
                lesson_string = "[" + str(lesson.id) + "]" + lesson.to_str()
                print(lesson_string)

if __name__ == "__main__":
    main()
