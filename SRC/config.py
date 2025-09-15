LANGUAGE = {
    'l_language': {'ru': 'Язык', 'en': 'Language'},
    'pb_help': {'ru': 'Помощь', 'en': 'Help'},
    'l_token': {'ru': 'Токен доступа Вашего Яндекс.Диска:', 'en': 'Your Yandex.Disk access token:'},
    'l_local': {'ru': 'Локальная папка:', 'en': 'Local folder:'},
    'l_yddir': {'ru': 'Папка на Яндекс.Диске:', 'en': 'Yandex.Disk folder:'},
    'l_ignoreextension': {'ru': 'Игнорировать файлы с расширением:', 'en': 'Ignore files with the extension:'},
    'l_ignorefiles': {'ru': 'Игнорировать файлы:', 'en': 'Ignore files:'},
    'l_logsize': {'ru': 'Размер лог-файла не более:', 'en': 'The size of the log file:'},
    'l_kb': {'ru': 'КБ', 'en': 'Kb'},
    'pb_openlog': {'ru': 'Открыть лог-файл', 'en': 'Open log-file'},
    'l_timesync': {'ru': 'Синхронизировать через:', 'en': 'Synchronization time:'},
    'l_sec': {'ru': 'СЕК', 'en': 'SEC'},
    'pb_start': {'ru': 'Начать синхронизацию', 'en': 'Start sync'},
    'pb_stop': {'ru': 'Остановить', 'en': 'Stop sync'},
    'exit': {'ru': 'Выход', 'en': 'Exit'},
    'open': {'ru': 'Открыть окно', 'en': 'Open Window'},
    'add_folder': {'ru': 'Добавить папку', 'en': 'Add folder'},
    'add_files': {'ru': 'Добавить файлы', 'en': 'Add files'},
}

CONFIG_DEFAULT = {
    'language': 'ru',
    'token': '',
    'local': '',
    'yddir': '',
    'ignoreextensions': [],
    'ignorefiles': [],
    'logsize': 1024,
    'timesync': 60,
}

tray_menu_style = """
            QMenu {
                background-color: #2c3e50;
                color: white;
                border: 1px solid #34495e;
                border-radius: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                border-bottom: 1px solid #34495e;
            }
            QMenu::item:selected {
                background-color: #3498db;
            }
            QMenu::item:disabled {
                color: #7f8c8d;
            }
        """