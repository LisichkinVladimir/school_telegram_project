"""
Модуль данных сессии бота
"""
import logging
from telegram.ext import ContextTypes
from schedule_parser import Schedules
import config as cfg

class BotData:
    """
    Данные сессии бота
    """
    def __init__(self):
        self.__schedules: Schedules = None

    @property
    def schedules(self) -> Schedules:
        if self.__schedules is None:
            self.__schedules = Schedules()
            # TODO сделать хранение и получение данных в SqLite
            self.__schedules.parse(cfg.SCHEDULE_URL)
        return self.__schedules

def create_schedules(context: ContextTypes.DEFAULT_TYPE) -> None:
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

def get_schedules(context: ContextTypes.DEFAULT_TYPE) -> Schedules:
    """
    Получить расписания
    """
    create_schedules(context)
    if context.bot_data is not None and "BotData" in context.bot_data:
        logging.info("Get schedules from bot_data")
        return context.bot_data["BotData"].schedules
    elif context.user_data is not None and "BotData" in context.user_data:
        logging.info("Get schedules from user_data")
        return context.user_data["BotData"].schedules
    else:
        logging.info("Context bot_data and user_data is none")
        return BotData().schedules()

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
