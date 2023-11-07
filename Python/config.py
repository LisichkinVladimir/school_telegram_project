"""
Модуль настроек бота
"""
import os
import logging

BOT_TOKEN = os.getenv("BOT_TOKEN")
if BOT_TOKEN is None:
    logging.info(f"BOT_TOKEN is Nome")
    BOT_TOKEN = "APAK_dNuJQb2XLJGOf_xEw_hC9b8qhOPEAA:0710988466"[::-1]
SCHEDULE_URL = "https://1502.mskobr.ru/uchashimsya/raspisanie-kanikuly"

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
