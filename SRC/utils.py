
def get_time(time_sync: float) -> str:
    """Функция преобразует полученную длину песни в формат 00:00:00"""
    temp, secs = divmod(int(time_sync), 60)
    hours, minuts = divmod(int(temp), 60)
    return f'{hours:02d}:{minuts:02d}:{secs:02d}'



