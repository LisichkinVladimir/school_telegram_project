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
import requests
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage
from telegram.constants import ParseMode
import pdfplumber
from cache_func import timed_lru_cache, hash_string_to_byte
import config as cfg

class LessonIdent:
    """
    Идентификатор урока
    """
    def __init__(self, week: int, hour_start: str, day_of_week: str):
        """
        Конструктор класса
        week: чередование по неделям
        hour: час начала урока
        day_of_week: день недели
        """
        self.__week: int = week
        self.__hour_start: str = hour_start
        self.__day_of_week: str = day_of_week
        # идентификатор
        self.__id = hash(self)

    def __hash__(self) -> int:
        """ Вычисление хеша """
        return hash_string_to_byte(f"{self.__week}_{self.__hour_start}_{self.__day_of_week}")

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

    def __init__(self, ident: LessonIdent, name: str, office: str, group: str, teacher: str, row_data: str = None):
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
        self.__row_data: str = row_data
        self.__groups: list = []
        self.__id: int = hash_string_to_byte(f"{self.__name}_{self.ident.week}_{self.ident.hour_start}_{self.ident.day_of_week}")

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
            for group_item in self.groups:
                result = f"{result} // {group_item.name}"
                if self.PRINT_OFFICE in what_to_print and group_item.office:
                    result = f"{result} каб.{group_item.office}"
                if self.PRINT_GROUP in what_to_print and group_item.group:
                    result = f"{result} гр. {group_item.group}"
                if self.PRINT_TEACHER in what_to_print and group_item.teacher:
                    result = f"{result} {group_item.teacher}"
        return result.strip()

class WayOfWeek:
    """
    Вспомогательный класс предназначенный для поиска строи или столбцов дней недели
    """
    short_week_names: list = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
    week_names: list = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']

    def __init__(self, tables: list):
        """
        Конструктор класса
        """
        # Словарь с найденными днями неделями
        self.__has_week: bool = False
        self.__row_index: int = -1
        self.__column_index: int = -1
        self.__week_indexes: dict = {}
        for table in tables:
            self.__has_week = False
            if len(table) > 0:
                # Получение индексов дней недели
                for i, row in enumerate(table):
                    for j, col in enumerate(row):
                        index = self.week_names.index(col) if col in self.week_names else None
                        if index is not None:
                            self.__week_indexes[self.week_names[index]] = (i, j)
                            self.__has_week = True
                        else:
                            index = self.short_week_names.index(col) if col in self.short_week_names else None
                            if index is not None:
                                self.__week_indexes[self.short_week_names[index]] = (i, j)
                                self.__has_week = True
                if self.__has_week:
                    logging.info(f"week_indexes={self.__week_indexes}")
                    # Определение - дни недели по строкам или столбцам
                    self.__row_index = next(iter(self.__week_indexes.values()))[0]
                    self.__column_index = next(iter(self.__week_indexes.values()))[1]
                    for value in self.__week_indexes.values():
                        if self.__row_index != value[0]:
                            self.__row_index = -1
                        if self.__column_index != value[1]:
                            self.__column_index = -1

    def get_dey_of_week_by_row(self, row_index: int) -> str:
        """
        Поиск дня недели по индексу столбца
        """
        for key, value in self.__week_indexes.items():
            if value[0] == row_index:
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
    def week_indexes(self) -> dict:
        """ Индексы ячеек дней неделей """
        return self.__week_indexes

class WeekSchedule:
    """
    Расписание класса на неделю/две недели
    """
    def __init__(self, url: str):
        """
        Конструктор класса
        class_name: название класса
        department: корпус
        url: url pdf файла
        created: str: дата создания
        """
        self.__class_name: str = None
        self.__department: str = None
        self.__url: str = url
        self.__created = None
        self.__hash: str = ""
        self.__last_parse_result = False
        self.__lesson_dict = {}

    def __parse_lesson(self, lesson: str, week, hour, day_of_week: str) -> None:
        """
        Разобрать lesson - достать name/office/group
        """
        row_data = lesson
        lesson = lesson.replace("\n", " ")
        # group
        group = None
        if self.__class_name in lesson:
            s = self.__class_name + R".\d{1}"
            match = re.search(RF"{s}", lesson)
            if match:
                group = lesson[match.start():match.end()]
                lesson = lesson.replace(group, "")
            else:
                s = self.__class_name + R"\d{1}"
                match = re.search(RF"{s}", lesson)
                if match:
                    group = lesson[match.start():match.end()]
                    lesson = lesson.replace(group, "")
        # office
        office = None
        match = re.search(R"\d+\D{0,1}", lesson)
        if match:
            office = lesson[match.start():match.end()].strip()
            lesson = lesson.replace(office, "").strip()
        # teacher
        teacher = None
        match = re.search(R"\s[а-яА-Я]+\s\D\.\D\.", lesson)
        if match:
            teacher = lesson[match.start():].strip()
            lesson = lesson.replace(teacher, "").strip()
        name = lesson
        logging.info(f"day_of_week={day_of_week} lesson={name} group={group} office={office} teacher={teacher}")
        lesson_ident: LessonIdent = LessonIdent(week, hour, day_of_week)
        new_lesson = Lesson(ident = lesson_ident, name = name, office = office, group = group, teacher = teacher, row_data = row_data)
        if lesson_ident not in self.__lesson_dict:
            self.__lesson_dict[lesson_ident] = new_lesson
        else:
            # Разбиение урока на группы
            lesson: Lesson = self.__lesson_dict[lesson_ident]
            lesson.groups.append(new_lesson)

    def __parse_week_by_row(self, table: list, day_of_week: WayOfWeek) -> bool:
        """
        Разбор расписания где дни недели по строкам к строке row_index
        """
        first_column = next(iter(day_of_week.week_indexes.values()))[1]
        hour_index = first_column - 1
        week_index = None
        if hour_index >= 1:
            week_index = hour_index - 1
        week = 1
        # Цикл по часам i - столбец
        for i in range(first_column, len(table)):
            hour = int(table[i][hour_index])
            if week_index is not None and table[i][week_index] is not None:
                week = int(table[i][week_index])
            logging.info(f"week={week} hour={hour}")
            # Цикл по дням недели
            for j in range(hour_index + 1, len(table[i])):
                day = day_of_week.get_dey_of_week_by_row(j)
                if day is None:
                    day = day_of_week.get_dey_of_week_by_row(j-1)
                if day:
                    lesson = table[i][j]
                    if lesson is not None and lesson != '':
                        # Есть урок
                        self.__parse_lesson(lesson, week, hour, day)
                        self.__last_parse_result = True
                    elif i > 2 and table[i-1][j]:
                        # lesson is None но предыдущий столбец есть
                        prev_row_data = table[i-1][j]
                        lesson_ident: LessonIdent = LessonIdent(week, hour-1, day_of_week)
                        if lesson_ident in self.__lesson_dict:
                            lesson: Lesson = self.__lesson_dict[lesson_ident]
                            if lesson.row_data == prev_row_data:
                                lesson.hour_end = hour
                            elif len(lesson.groups) > 0:
                                for group in lesson.groups:
                                    if group.row_data == prev_row_data:
                                        group.hour_end = hour
        return self.__last_parse_result

    @timed_lru_cache(60*60*24)
    def parse(self) -> bool:
        """
        Процедура разбора url расписания
        """
        # Получение html из Web
        logging.info(f"get {self.__url}")
        response = requests.get(self.__url)
        if response.status_code != 200:
            logging.error(f"Error get {self.__url}. error code {response.status_code}")
            return False

        # Вычисление хэша
        new_hash = md5(response.content).hexdigest()
        logging.info(f"hash {new_hash}")
        if self.__hash == new_hash:
            return self.__last_parse_result

        self.__hash = new_hash
        self.__lesson_dict = {}
        self.__class_name = None
        self.__department = None
        self.__created = None
        self.__last_parse_result = False

        mem_obj = io.BytesIO(response.content)
        pdfReader = PdfReader(mem_obj)
        # printing number of pages in pdf file
        pages = len(pdfReader.pages)
        if pages == 0:
            logging.error("Error parse pdf. Zero page number")
            return False
        logging.info(f"Pdf pages {pages}")
        # extract page structure
        layouts = extract_pages(mem_obj)
        pages_num = 0
        element_num = 0
        self.__class_name = self.__url[self.__url.rfind('/') + 1:]
        self.__class_name = unquote(self.__class_name)
        self.__class_name = self.__class_name.replace(".pdf", "")
        for page_layout in layouts:
            if isinstance(page_layout, LTPage):
                pages_num += 1
                element_num = 0
            for element in page_layout:
                element_num += 1
                if isinstance(element, LTTextContainer):
                    s = element.get_text()
                    if pages_num == 1 and element_num in [1, 2] and ("Школа №1502" in s or "Школа № 1502" in s):
                        self.__department = s
                        self.__department = self.__department.replace('ГБОУ "Школа №1502",', '').strip()
                        self.__department = self.__department.replace('ГБОУ "Школа № 1502",', '').strip()
                        self.__department = self.__department.replace('при МЭИ', '').strip()
                    if s.find("Составлено:") >= 0:
                        match = re.search(R"\d{1,2}\.\d{1,2}\.\d{4}", s)
                        if match:
                            self.__created = datetime.strptime(s[match.start():match.end()], "%d.%m.%Y")
        logging.info(f"class={self.__class_name} department={self.__department} created={self.__created}")

        # extract table
        pdf = pdfplumber.open(mem_obj)
        for page_num in range(0, pages):
            table_page = pdf.pages[page_num]
            tables = table_page.extract_tables()
            for table in tables:
                if len(table) > 0:
                    # Получение индексов дней недели
                    day_of_wek: WayOfWeek = WayOfWeek(tables)
                    if day_of_wek.has_week:
                        if day_of_wek.row_index >= 0 and day_of_wek.column_index == -1:
                            logging.info(f"week indexes by row {day_of_wek.row_index}")
                            return self.__parse_week_by_row(table, day_of_wek)
                        elif day_of_wek.column_index >= 0 and day_of_wek.row_index == -1:
                            logging.info(f"week indexes by column {day_of_wek.column_index}")
                        else:
                            logging.error("Can not find day of week in table")
                            return False

                    """

                if has_week == week_location.ROW:
                    # Дни недели в строке
                    logging.info(f"week on row indexes {week_indexes}")
                    hour_index = week_indexes[0] - 1
                    week_index = None
                    if hour_index >= 1:
                        week_index = hour_index - 1
                    week = 1
                    # Цикл по часам i - столбец
                    for i in range(2, len(table)):
                        hour = int(table[i][hour_index])
                        if week_index is not None and table[i][week_index] is not None:
                            week = int(table[i][week_index])
                        logging.info(f"week={week} hour={hour}")
                        # Цикл по дням недели j - строчка
                        for j in range(hour_index + 1, len(table[i])):
                            day_of_week = None
                            index = week_indexes.index(j) if j in week_indexes else None
                            if index is not None:
                                day_of_week = week_names[index]
                            else:
                                index = week_indexes.index(j - 1) if j - 1 in week_indexes else None
                                if index is not None:
                                    day_of_week = week_names[index]
                            if day_of_week:
                                lesson = table[i][j]
                                if lesson is not None and lesson != '':
                                    # Есть урок
                                    self.__parse_lesson(lesson, week, hour, day_of_week)
                                    self.__last_parse_result = True
                                elif i > 2 and table[i-1][j]:
                                    # lesson is None но предыдущий столбец есть
                                    prev_row_data = table[i-1][j]
                                    lesson_ident: LessonIdent = LessonIdent(week, hour-1, day_of_week)
                                    if lesson_ident in self.__lesson_dict:
                                        lesson: Lesson = self.__lesson_dict[lesson_ident]
                                        if lesson.row_data == prev_row_data:
                                            lesson.hour_end = hour
                                        elif len(lesson.groups) > 0:
                                            for group in lesson.groups:
                                                if group.row_data == prev_row_data:
                                                    group.hour_end = hour
                elif len(table)>1:
                    # Дни недели в столбце
                    logging.info("week on column")
                    # Получение индексов дней недели
                    for j in range(2, len(table)):
                        week = table[j][0]
                        i = week_names.index(week) if week in week_names else None
                        if i is not None:
                            week_indexes[i] = j
                            has_week_column = True
                    logging.info(f"week on row column {week_indexes}")
                    if has_week_column:
                        # TODO
                        pass
        """
        return self.__last_parse_result

    def week_list(self) -> list:
        """
        Список чередования по неделям
        """
        result = []
        for key in self.__lesson_dict:
            if key.week not in result:
                result.append(key.week)
        return result

    def day_of_week_list(self, week: int) -> list:
        """
        Список учебных дней недели
        """
        result = []
        for key in self.__lesson_dict:
            if key.week == week and key.day_of_week not in result:
                result.append(key.day_of_week)
        return result

    def lesson_list(self, week: int, day_of_week: str) -> list:
        """
        Список уроков дня
        """
        result = []
        for key, value in self.__lesson_dict.items():
            if key.week == week and key.day_of_week == day_of_week:
                result.append(value)
        return result

    @property
    def hash(self) -> str:
        """ Свойство хэш pdf """
        return self.__hash

    @property
    def department(self) -> str:
        """ Свойство корпус """
        return self.__department

    @property
    def class_name(self) -> str:
        """ Свойство имя класса """
        return self.__class_name

    @property
    def url(self) -> str:
        """ Свойство url pdf файла """
        return self.__url

    @property
    def last_parse_result(self) -> bool:
        """ Был ли разбор успешен """
        return self.__last_parse_result

def main():
    """
    Разбора pdf расписания класса
    """
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    cfg.disable_logger(["pdfminer.psparser", "pdfminer.pdfparser", "pdfminer.pdfinterp", "pdfminer.cmapdb", "pdfminer.pdfdocument", "pdfminer.pdfpage"])
    url = "https://1502.mskobr.ru/files/rasp/alpha/7%D0%95.pdf"
    #url = "https://1502.mskobr.ru//files/rasp/delta3/2%D0%BE.pdf"
    week_schedule = WeekSchedule(url)
    week_schedule.parse()
    print("----------------------------------------------")
    for week in week_schedule.week_list():
        for day_of_week in week_schedule.day_of_week_list(week):
            print(f"week-{week} day_of_week-{day_of_week}")
            for lesson in week_schedule.lesson_list(week, day_of_week):
                lesson_string = "[" + str(lesson.id) + "]" + lesson.to_str()
                print(lesson_string)

if __name__ == "__main__":
    main()
