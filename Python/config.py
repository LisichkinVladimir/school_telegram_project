"""
Модуль настроек бота
"""
import os
import sys
import logging

# Запуск логирования
if not logging.getLogger().hasHandlers():
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    logging.info("BOT_TOKEN is None")
else:
    logging.info("BOT_TOKEN is not None")
BASE_URL = "https://1502.mskobr.ru"
SCHEDULE_URL = f"{BASE_URL}/uchashimsya/raspisanie-kanikuly"

def disable_logger(log_list: list) -> None:
    """
    Отключает логирование для выбранных модулей
    """
    for log in log_list:
        logging.getLogger(log).disabled = True

def get_data_path() -> str:
    """
    Место расположения данных приложения
    """
    path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Место расположения данных приложения
    db_path = f"{path}/data/"
    if not os.path.exists(db_path):
        # создаем директорию
        os.mkdir(db_path)
    return db_path

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
