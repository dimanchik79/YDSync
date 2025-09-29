import json
import re
import platform
import sys

import logging
import threading
import time

from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QAction, QMenu, QFileDialog, QDialog

from watchdog.observers import Observer

from SRC.config import LANGUAGE
from SRC.utils import get_time
from SRC.config import tray_menu_style, qlineedit_style_error, qlineedit_style, windows_drive_pattern

from SRC.services import YandexDiskSync, FileChangeHandler

CONFIGURE = json.load(open("config.json", "r"))

# инициализируем логгер
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            'yd_sync.log',
            maxBytes=(CONFIGURE['logsize'] * 1024),
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('YandexDiskSync')

class YesNoDialog(QDialog):
    def __init__(self, text: str) -> None:
        super().__init__()
        uic.loadUi("GUI/yesno.ui", self)
        self.setFixedSize(400, 132)
        self.prompt.setText(text)

    def get_result(self):
        return self.exec_() == QDialog.Accepted

class SyncWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        self.sync_service = None
        self.observer = None
        self.event_handler = None

        self.loop = False # Запуск цикла синхронизации
        self.sync_time = 0 # Таймер синхронизации

        uic.loadUi("GUI/mainwindow.ui", self)
        self.setFixedSize(699, 531)

        # Tray menu
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon("GUI/icon.ico"))
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        show_action = QAction(LANGUAGE['open'][CONFIGURE['language']], self)
        show_action.triggered.connect(self.show)
        exit_action = QtWidgets.QAction(LANGUAGE['exit'][CONFIGURE['language']], self)
        exit_action.triggered.connect(self.exit_program)
        tray_menu = QMenu(self)
        tray_menu.setStyleSheet(tray_menu_style)

        tray_menu.addAction(show_action)
        tray_menu.addAction(exit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

        # Signals
        self.r_rus.clicked.connect(lambda: self.language_set("ru"))
        self.r_eng.clicked.connect(lambda: self.language_set("en"))
        self.pb_local.clicked.connect(self.add_folder)
        self.pb_start.clicked.connect(self.start_sync)
        self.pb_stop.clicked.connect(self.stop_sync)
        self.pb_ignorefiles.clicked.connect(self.add_files)

        self.le_local.textChanged.connect(lambda: self.le_local.setStyleSheet(qlineedit_style))

        # Buttons
        self.pb_start.setEnabled(True)
        self.pb_stop.setEnabled(False)

        self.set_from_config()
        threading.Thread(target=self.synchronize, args=(), daemon=True).start()

    def start_sync(self) -> None:
        """Метод запускает цикл синхронизации"""

        self.l_prompt.setText(LANGUAGE['connect'][CONFIGURE['language']])

        path = Path(self.le_local.text())
        if re.match(windows_drive_pattern, str(path)) and platform.system() == 'Windows':
            if path.exists():
                self.create_sync_service()
        else:
            self.le_local.setStyleSheet(qlineedit_style_error)
            self.le_local.setFocus()
            self.l_prompt.setText(LANGUAGE['error'][CONFIGURE['language']])
            logger.error(LANGUAGE['error'][CONFIGURE['language']])
            return

        self.pb_start.setEnabled(False)
        self.pb_stop.setEnabled(True)

        self.loop = True
        self.sync_time = 0

        # Запуск наблюдателя
        self.observer.start()

        msg = LANGUAGE['sync_begin'][CONFIGURE['language']]
        logger.info(msg)
        self.l_prompt.setText(msg)

    def stop_sync(self) -> None:
        """Метод останавливает цикл синхронизации"""
        self.pb_start.setEnabled(True)
        self.pb_stop.setEnabled(False)
        self.loop = False
        self.observer.stop()
        self.observer.join()
        msg = LANGUAGE['sync_end'][CONFIGURE['language']]
        logger.info(msg)
        self.l_prompt.setText(msg)

    def on_tray_icon_activated(self, reason) -> None:
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick: # type: ignore
            self.show()

    def exit_program(self) -> None:
        """Метод закрывает окно программы"""
        self.save_config()
        json.dump(CONFIGURE, open('config.json', 'w'), indent=4)
        sys.exit()

    def closeEvent(self, event) -> None:
        """Метод вызывает метод выхода из программы"""
        event.ignore()  # Не вызывать метод closeEvent
        self.hide()

    def create_sync_service(self) -> None:
        # Создание сервиса синхронизации
        try:
            self.sync_service = YandexDiskSync(self, logger, CONFIGURE, LANGUAGE)
            # Создание наблюдателя за изменениями в файлах
            self.event_handler = FileChangeHandler(self, self.sync_service, logger)
            self.observer = Observer()
            self.observer.schedule(self.event_handler, str(self.le_local.text()), recursive=True)
        except Exception as e:
            if e == 'Invalid Yandex.Disk token':
                self.l_prompt.setText(LANGUAGE['token_error'][CONFIGURE['language']])
                logger.error(LANGUAGE['token_error'][CONFIGURE['language']])
            else:
                self.l_prompt.setText(LANGUAGE['error'][CONFIGURE['language']])
                logger.error(LANGUAGE['error'][CONFIGURE['language']])

    def language_set(self, language: str) -> None:
        """Метод устанавливает язык интерфейса"""
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
        self.pb_start.setText(LANGUAGE['pb_start'][language])
        self.pb_stop.setText(LANGUAGE['pb_stop'][language])
        CONFIGURE['language'] = language

    def set_from_config(self) -> None:
        """Метод устанавливает значения полей из файла конфигурации"""
        extensions, files = '', ''
        if CONFIGURE['language'] == 'ru':
            self.r_rus.setChecked(True)
        if CONFIGURE['language'] == 'en':
            self.r_eng.setChecked(True)
        self.language_set(CONFIGURE['language'])

        self.le_token.setText(CONFIGURE['token'])
        self.le_local.setText(CONFIGURE['local'])
        self.le_yddir.setText(CONFIGURE['yddir'])
        if CONFIGURE['ignoreextensions']:
            extensions = ', '.join(CONFIGURE['ignoreextensions'])
        if CONFIGURE['ignorefiles']:
            files = ', '.join(CONFIGURE['ignorefiles'])
        self.le_ignoreextension.setText(extensions)
        self.le_ignorefiles.setText(files)
        self.le_logsize.setText(str(CONFIGURE['logsize']))

    def add_folder(self) -> None:
        """Метод добавляет папку для синхронизации"""
        local = QFileDialog.getExistingDirectory(self,
                                                 LANGUAGE['add_folder'][CONFIGURE['language']],
                                                 "")
        if local:
            CONFIGURE['local'] = local
            yddir = "/" + Path(local).name
            self.le_local.setText(local)
            self.le_yddir.setText(yddir)

    def add_files(self) -> None:
        default_path = Path(CONFIGURE['local']) if CONFIGURE['local'] else ''
        files = QFileDialog.getOpenFileNames(self,
                                             LANGUAGE['add_files'][CONFIGURE['language']],
                                             directory=str(default_path))[0]
        if files:
            files_name = [Path(path).name for path in files]
            print(files_name)
            CONFIGURE['ignorefiles'] = files_name
            self.le_ignorefiles.setText(', '.join(name for name in files_name))

    def save_config(self) -> None:
        CONFIGURE['token'] = self.le_token.text() if self.le_token.text() else ''

    def synchronize(self) -> None:
        while True:
            time.sleep(1)
            if self.loop:
                self.l_time.setText(get_time(self.sync_time))
                self.sync_time += 1
