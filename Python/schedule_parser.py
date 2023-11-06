"""
Модуль разбора учебного расписания
"""
import logging
import requests
import sys
import re
from bs4 import BeautifulSoup
import config as cfg
class SchoolClass:
    """
    Школьный класс
    """
    def __init__(self, name: str, link: str):
        """
        Конструктор класса
        name: название класса
        link: ссылка на pdf файл, содержащий расписание
        """
        self.__name: str = name
        match = re.search(R"^\d{1,2}", name)
        self.__number: int = None
        if match and name[:match.end()].isnumeric():
            self.__number = int(name[:match.end()])
        self.__link: str = link

    @property
    def name(self) -> str:
        return self.__name

    @property
    def number(self) -> int:
        return self.__number

    @property
    def link(self) -> str:
        return self.__link

class Schedule:
    """
    Класс расписание
    """
    def __init__(self, department: str):
        self.__department: str = department
        self.__classes: list = []

    def add_class(self, class_: SchoolClass):
        self.__classes.append(class_)

    @property
    def department(self) -> str:
        return self.__department

    @property
    def class_list(self) -> list:
        return self.__classes

class Schedules:
    """
    Класс расписания
    """
    def __init__(self):
        self.__list: list = []

    def parse(self, url: str) -> bool:
        # Получение html из Web
        response = requests.get(url)
        if response.status_code != 200:
            logging.error(f"Error get {url}. error code {response.status_code}")
            return False
        data = response.text
        logging.info(f"get {data[:20]}...\n")

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
                schedule = Schedule(h3.text)

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
                                    class_ = SchoolClass(col.text, url)
                                    if class_.number is not None or url is not None:
                                        schedule.add_class(class_)

                self.__list.append(schedule)
        return len(self.__list) > 0

    @property
    def list(self) -> list:
        return self.__list

def main():
    """
    Разбора учебного расписания
    """
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    schedules = Schedules()
    schedules.parse(cfg.SCHEDULE_URL)
    print("----------------------------------------------")
    for schedule in schedules.list:
        print(schedule.department)
        for class_ in schedule.class_list:
            print(f"{class_.name};", end="")
        print("\n")

if __name__ == "__main__":
    main()
