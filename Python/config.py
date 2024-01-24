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
    db_path = os.getenv("PERSISTENCE_MOUNT")
    if db_path is None:
        db_path = "../&ScriptDir/data"
    if "&ScriptDir" in db_path:
        path = os.path.dirname(os.path.abspath(__file__))
        str = db_path.partition("&ScriptDir")
        prefix = str[0]
        postfix = str[2]
        for s in prefix.split("/"):
            if s == "..":
                path = os.path.dirname(path)
        db_path = path + postfix
    logging.info(f"db_path:{db_path}")
    if not os.path.exists(db_path):
        # создаем директорию
        os.mkdir(db_path)
    else:
        files = [f for f in os.listdir(db_path) if os.path.isfile(os.path.join(db_path, f))]
        logging.info(f"files:\n{files}")
        # Временный код
        if os.path.exists("/data"):
            files = [f for f in os.listdir("/data") if os.path.isfile(f)]
            logging.info(f"files:\n{files}")
    return db_path

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
