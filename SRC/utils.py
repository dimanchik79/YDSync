import time

def get_time(time_sync: int) -> str:
    days = time_sync // (24 * 3600)
    seconds = time_sync % (24 * 3600)
    hours = time_sync // 3600
    seconds %= 3600
    minutes = time_sync // 60
    time_sync %= 60

    # Форматируем с ведущими нулями
    return f"{days:02d}:{hours:02d}:{minutes:02d}:{time_sync:02d}"



