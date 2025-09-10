import json
import sys
from distutils.command.config import config

from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QAction, QMenu

from config import LANGUAGE


class Window(QMainWindow):
    CONFIG = json.load(open("config.json", "r"))

    def __init__(self) -> None:
        super().__init__()
        uic.loadUi("GUI/mainwindow.ui", self)
        self.setFixedSize(699, 450)

        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon("GUI/icon.ico"))
        self.tray_icon.activated.connect(self.on_tray_icon_activated)

        show_action = QAction(LANGUAGE['open'][self.CONFIG['language']], self)
        show_action.triggered.connect(self.show)


        exit_action = QtWidgets.QAction(LANGUAGE['exit'][self.CONFIG['language']], self)
        exit_action.triggered.connect(self.exit_program)

        tray_menu = QMenu(self)
        tray_menu.addAction(show_action)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        self.r_rus.clicked.connect(lambda: self.language_set("ru"))
        self.r_eng.clicked.connect(lambda: self.language_set("en"))

        self.set_from_config()


    def on_tray_icon_activated(self, reason) -> None:
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick: # type: ignore
            self.show()

    def exit_program(self):
        """Метод закрывает окно программы"""
        json.dump(self.CONFIG, open('config.json', 'w'), indent=4)
        sys.exit()

    def closeEvent(self, event) -> None:
        """Метод вызывает метод выхода из программы"""
        event.ignore()  # Не вызывать метод closeEvent
        json.dump(self.CONFIG, open('config.json', 'w'), indent=4)
        self.hide()

    def language_set(self, language):
        self.l_language.setText(LANGUAGE['l_language'][language])
        self.pb_help.setText(LANGUAGE['pb_help'][language])
        self.l_token.setText(LANGUAGE['l_token'][language])
        self.l_local.setText(LANGUAGE['l_local'][language])
        self.l_yddir.setText(LANGUAGE['l_yddir'][language])
        self.l_ignoreextension.setText(LANGUAGE['l_ignoreextension'][language])
        self.l_ignorefiles.setText(LANGUAGE['l_ignorefiles'][language])
        self.l_logsize.setText(LANGUAGE['l_logsize'][language])
        self.l_kb.setText(LANGUAGE['l_kb'][language])
        self.pb_openlog.setText(LANGUAGE['pb_openlog'][language])
        self.l_timesync.setText(LANGUAGE['l_timesync'][language])
        self.l_sec.setText(LANGUAGE['l_sec'][language])
        self.pb_start.setText(LANGUAGE['pb_start'][language])
        self.pb_stop.setText(LANGUAGE['pb_stop'][language])
        self.CONFIG['language'] = language

    def set_from_config(self):
        extensions, files = '', ''
        if self.CONFIG['language'] == 'ru':
            self.r_rus.setChecked(True)
        if self.CONFIG['language'] == 'en':
            self.r_eng.setChecked(True)
        self.language_set(self.CONFIG['language'])

        self.le_token.setText(self.CONFIG['token'])
        self.le_local.setText(self.CONFIG['local'])
        self.le_yddir.setText(self.CONFIG['yddir'])
        if self.CONFIG['ignoreextensions']:
            extensions = ','.join(self.CONFIG['ignoreextensions'])
        if self.CONFIG['ignorefiles']:
            files = ','.join(self.CONFIG['ignorefiles'])
        self.le_ignoreextension.setText(extensions)
        self.le_ignorefiles.setText(files)
        self.le_logsize.setText(str(self.CONFIG['logsize']))
        self.le_timesync.setText(str(self.CONFIG['timesync']))



