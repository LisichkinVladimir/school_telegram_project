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

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
