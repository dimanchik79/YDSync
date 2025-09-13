import sys
import json
import logging
from os import path
from logging.handlers import RotatingFileHandler

from PyQt5 import QtWidgets
from GUI.gui import Window

from SRC.config import CONFIG_DEFAULT

# загружаем конфиг
if not path.exists('config.json'):
    json.dump(CONFIG_DEFAULT, open('config.json', 'w'), indent=4)

configure = json.load(open("config.json", "r"))

# инициализируем логгер
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'yd_sync.log', 
            maxBytes=(configure['logsize'] * 1024),
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('YandexDiskSync')


def main():
    """Запуск приложения"""
    app = QtWidgets.QApplication(sys.argv)
    window = Window(configure)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    exit(main())