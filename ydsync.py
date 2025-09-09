import sys

from PyQt5 import QtWidgets
from GUI.gui import Window


def main():
    app = QtWidgets.QApplication(sys.argv)
    window = Window()
    window.show()  # Это выводит окно на экран
    sys.exit(app.exec_())

if __name__ == "__main__":
    exit(main())