import sys
from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QAction, QMenu


class Window(QMainWindow):
    """Модель инициализации интерфейса плейера
    play_list: dict -

    """

    def __init__(self) -> None:
        super().__init__()
        uic.loadUi("GUI/mainwindow.ui", self)
        self.setFixedSize(699, 450)

        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon("GUI/icon.ico"))
        self.tray_icon.activated.connect(self.onTrayIconActivated)

        show_action = QAction("Настройки", self)
        show_action.triggered.connect(self.show)


        exit_action = QtWidgets.QAction("Выход", self)
        exit_action.triggered.connect(self.exit_program)

        tray_menu = QMenu(self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def onTrayIconActivated(self, reason) -> None:
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick: # type: ignore
            self.show()

    @staticmethod
    def exit_program():
        """Метод закрывает окно программы"""
        sys.exit()
