import sys
import json
from os import path

from PyQt5 import QtWidgets
from GUI.gui import Window

from config import CONFIG_DEFAULT


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    if not path.exists('config.json'):
        json.dump(CONFIG_DEFAULT, open('config.json', 'w'), indent=4)
    exit(main())