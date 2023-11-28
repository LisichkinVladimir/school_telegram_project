"""
Модуль кеширования
"""
from functools import lru_cache, wraps
from datetime import datetime, timedelta

def timed_lru_cache(seconds: int, maxsize: int = 128):
    """
    Декоратор кеширования по времени и кол-ву вызовов
    """

    def wrapper_cache(func):
        func = lru_cache(maxsize=maxsize)(func)
        func.lifetime = timedelta(seconds=seconds)
        func.expiration = datetime.utcnow() + func.lifetime


        @wraps(func)
        def wrapped_func(*args, **kwargs):
            if datetime.utcnow() >= func.expiration:
                func.cache_clear()
                func.expiration = datetime.utcnow() + func.lifetime
            return func(*args, **kwargs)

        return wrapped_func

    return wrapper_cache

def hash_string_to_byte(s: str) -> int:
    """
    Хеширование строки в байт
    """
    byte_array = bytes(s, encoding='utf-8')
    result: int = 5381
    for byte in byte_array:
        result = (((result << 5) + result) + byte) & 0xFFFF
    return result

def hash_string(s: str) -> int:
    """
    Хеширование строки в два байта
    """
    byte_array = bytes(s, encoding='utf-8')
    result: int = 5381
    for byte in byte_array:
        result = (((result << 5) + result) + byte) & 0xFFFFFFFF
    return result

def main():
    raise SystemError("This file cannot be operable")

if __name__ == "__main__":
    main()
