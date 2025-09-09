import sys
from os import path

from PyQt5 import QtWidgets
from GUI.gui import Window


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    if not path.exists('config.json'):
        ...
        
    exit(main())