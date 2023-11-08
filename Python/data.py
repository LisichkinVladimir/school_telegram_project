"""
Модуль данных сессии бота
"""
from telegram.ext import ContextTypes
from schedule_parser import Schedules
import config as cfg

class BotData:
    """
    Данные сессии бота
    """
    def __init__(self, user: str):
        self.__user: str = user
        self.__schedules: Schedules = None

    @property
    def user(self) -> str:
        return self.__user

    @property
    def schedules(self) -> Schedules:
        if self.__schedules is None:
            self.__schedules = Schedules()
            # TODO сделать хранение и получение данных в SqLite
            self.__schedules.parse(cfg.SCHEDULE_URL)
        return self.__schedules

    def clear_schedules(self) -> None:
        self.__schedules = None

def get_schedules(context: ContextTypes.DEFAULT_TYPE) -> Schedules:
    """
    Получить расписания
    """
    bot_data: BotData = context.user_data["BotData"]
    return bot_data.schedules

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
