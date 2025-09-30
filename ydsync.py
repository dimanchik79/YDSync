import sys
import json
from os import path

from PyQt5 import QtWidgets
from SRC.synchranize import SyncWindow

from SRC.config import CONFIG_DEFAULT

# создание файла конфигурации
if not path.exists('config.json'):
    json.dump(CONFIG_DEFAULT, open('config.json', 'w'), indent=4)


def main():
    """Запуск GUI приложения"""
    app = QtWidgets.QApplication(sys.argv)
    window = SyncWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    exit(main())