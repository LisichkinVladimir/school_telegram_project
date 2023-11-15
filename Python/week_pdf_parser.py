"""
Модуль разбора недельного pdf расписания
"""
import sys
import io
import logging
import re
from datetime import datetime
import requests
from PyPDF2 import PdfReader
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage
import pdfplumber
import config as cfg

class LessonIdent:
    """
    Идентификатор урока
    """
    def __init__(self, week: int, hour_start: int, day_of_week: str):
        """
        Конструктор класса
        week: чередование по неделям
        hour: час начала урока
        day_of_week: день недели
        """
        self.__week: int = week
        self.__hour_start: int = hour_start
        self.__day_of_week: str = day_of_week

    def __hash__(self) -> int:
        """ Вычисление хеша """
        return hash(f"{self.__week}_{self.__hour_start}_{self.__day_of_week}")

    def __eq__(self, other) -> bool:
        """ Функция сравнения """
        return (self.__week == other.week) and (self.__hour_start == other.hour_start) and (self.__day_of_week == other.day_of_week)

    @property
    def week(self) -> int:
        """ Свойство чередование по неделям """
        return self.__week

    @property
    def hour_start(self) -> int:
        """ Свойство начало урока """
        return self.__hour_start

    @property
    def day_of_week(self) -> str:
        """ Свойство день недели """
        return self.__day_of_week

class Lesson:
    """
    Урок
    """
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
        self.__hour_end: int = ident.hour_start
        self.__name: str = name
        self.__office: str = office
        self.__group: str = group
        self.__teacher: str = teacher
        self.__row_data: str = row_data

    @property
    def ident(self) -> LessonIdent:
        """" Свойство идентификатор урока """
        return self.__ident

    @property
    def hour_end(self) -> int:
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
        self.__hash = None
        self.__lesson_dict = {}

    def parse(self) -> bool:
        """
        Процедура разбора url расписания
        """
        self.__hash = 0
        # Получение html из Web
        response = requests.get(self.__url)
        if response.status_code != 200:
            logging.error(f"Error get {self.__url}. error code {response.status_code}")
            return False
        self.__hash = hash(response.content)
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
        for page_layout in layouts:
            if isinstance(page_layout, LTPage):
                pages_num += 1
                element_num = 0
            for element in page_layout:
                element_num += 1
                if isinstance(element, LTTextContainer):
                    s = element.get_text()
                    if pages_num == 1 and element_num == 1:
                        self.__class_name = s
                        self.__class_name = self.__class_name.replace("\n", "")
                    if pages_num == 1 and element_num == 2:
                        self.__department = s
                        self.__department = self.__department.replace('ГБОУ "Школа №1502 при МЭИ",', '').strip()
                    if s.find("Составлено:") >= 0:
                        match = re.search(R"\d{1,2}\.\d{1,2}\.\d{4}", s)
                        if match:
                            self.__created = datetime.strptime(s[match.start():match.end()], "%d.%m.%Y")
        logging.info(f"class={self.__class_name} department={self.__department} created={self.__created}")
        # extract table
        pdf = pdfplumber.open(mem_obj)
        for page_num in range(0, pages):
            table_page = pdf.pages[page_num]
            week_names = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
            week_indexes = [None, None, None, None, None, None]
            tables = table_page.extract_tables()
            for table in tables:
                has_week_row = False
                index = 0
                if len(table) > 0:
                    # Получение индексов дней недели
                    for week in table[1]:
                        i = week_names.index(week) if week in week_names else None
                        if i is not None:
                            week_indexes[i] = index
                            has_week_row = True
                        index += 1
                logging.info(f"week indexes {week_indexes}")
                if has_week_row and len(table)>1:
                    hour_index = week_indexes[0] - 1
                    week_index = None
                    if hour_index >= 1:
                        week_index = hour_index - 1
                    week = 1
                    # Цикл по часам
                    for i in range(2, len(table)):
                        hour = int(table[i][hour_index])
                        if week_index is not None and table[i][week_index] is not None:
                            week = int(table[i][week_index])
                        logging.info(f"week={week} hour={hour}")
                        # Цикл по дням недели
                        for x, index in enumerate(week_indexes):
                            day_of_week = week_names[x]
                            lesson = table[i][index]
                            if lesson:
                                # Есть урок
                                row_data = lesson
                                lesson = lesson.replace("\n", " ")
                                # Разобрать lesson - достать name/office/group
                                # group
                                group = None
                                if self.__class_name in lesson:
                                    s = self.__class_name + R".\d{1}"
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
                                if lesson_ident not in self.__lesson_dict:
                                    self.__lesson_dict[lesson_ident] = Lesson(ident = lesson_ident, name = name, office = office, group = group, teacher = teacher, row_data = row_data)
                                else:
                                    lesson: Lesson = self.__lesson_dict[lesson_ident]
                                    lesson.hour_end = hour
                            elif i > 2 and table[i-1][index]:
                                # lesson is None но предыдущий столбец есть
                                prev_row_data = table[i-1][index]
                                lesson_ident: LessonIdent = LessonIdent(week, hour-1, day_of_week)
                                if lesson_ident in self.__lesson_dict:
                                    lesson: Lesson = self.__lesson_dict[lesson_ident]
                                    if lesson.row_data == prev_row_data:
                                        lesson.hour_end = hour
                                        self.__lesson_dict[lesson_ident] = lesson

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
    def hash(self) -> int:
        """ Свойство хэш pdf """
        return self.__hash

def main():
    """
    Разбора pdf расписания класса
    """
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    cfg.disable_logger(["pdfminer.psparser", "pdfminer.pdfparser", "pdfminer.pdfinterp", "pdfminer.cmapdb", "pdfminer.pdfdocument", "pdfminer.pdfpage"])
    url = "https://1502.mskobr.ru/files/rasp/alpha/7%D0%95.pdf"
    schedule = WeekSchedule(url)
    schedule.parse()
    print("----------------------------------------------")
    for week in schedule.week_list():
        for day_of_week in schedule.day_of_week_list(week):
            print(f"week-{week} day_of_week-{day_of_week}")
            for lesson in schedule.lesson_list(week, day_of_week):
                if lesson.hour_end == lesson.ident.hour_start:
                    print(f"{lesson.ident.hour_start}  {lesson.name} каб.{lesson.office}")
                else:
                    print(f"{lesson.ident.hour_start}-{lesson.hour_end} {lesson.name} каб.{lesson.office}")

if __name__ == "__main__":
    main()
