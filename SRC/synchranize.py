import json
import sys
import threading
import time

from pathlib import Path

import logging
from logging.handlers import RotatingFileHandler

import yadisk
from PyQt5 import uic, QtWidgets, QtGui
from PyQt5.QtWidgets import QMainWindow, QAction, QMenu, QFileDialog

from SRC.config import LANGUAGE
from SRC.utils import get_time
from SRC.config import tray_menu_style

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


class SyncWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        self.loop = False # Запуск цикла синхронизации
        self.sync_time = 0 # Время последней синхронизации
        
        uic.loadUi("GUI/mainwindow.ui", self)
        self.setFixedSize(699, 450)

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

        # Buttons
        self.pb_start.setEnabled(True)
        self.pb_stop.setEnabled(False)

        self.set_from_config()
        threading.Thread(target=self.synchronize, args=(), daemon=True).start()

    def start_sync(self) -> None:
        """Метод запускает цикл синхронизации"""
        self.pb_start.setEnabled(False)
        self.pb_stop.setEnabled(True)
        msg = LANGUAGE['sync_begin'][CONFIGURE['language']]
        logger.info(msg)
        self.l_prompt.setText(msg)
        self.loop = True
        self.sync_time = 0

        # Инициализируем клиент Яндекс.Диска
        self.y = yadisk.YaDisk(token=CONFIGURE['token'])

        # Проверяем подключение
        if not self.y.check_token():
            errmsg = LANGUAGE['token_error'][CONFIGURE['language']]
            logger.error(errmsg)
            self.l_prompt.setText(errmsg)
            return

        # Создаем папку в облаке если не существует
        if not self.y.exists(CONFIGURE['yddir']):
            self.y.mkdir(CONFIGURE['yddir'])

    def stop_sync(self) -> None:
        """Метод останавливает цикл синхронизации"""
        self.pb_start.setEnabled(True)
        self.pb_stop.setEnabled(False)
        logger.info(LANGUAGE['sync_end'][CONFIGURE['language']])
        self.loop = False

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
        self.l_timesync.setText(LANGUAGE['l_timesync'][language])
        self.l_sec.setText(LANGUAGE['l_sec'][language])
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
        self.le_timesync.setText(str(CONFIGURE['timesync']))

    def add_folder(self) -> None:
        """Метод добавляет папку для синхронизации"""
        local = QFileDialog.getExistingDirectory(self, LANGUAGE['add_folder'][CONFIGURE['language']], "")
        CONFIGURE['local'] = local
        self.le_local.setText(local)

    def add_files(self) -> None:
        files = QFileDialog.getOpenFileNames(self, LANGUAGE['add_files'][CONFIGURE['language']], "")[0]
        if files:
            self.le_ignorefiles.setText(', '.join(Path(path).name for path in files))

    def save_config(self) -> None:
        CONFIGURE['token'] = self.le_token.text() if self.le_token.text() else ''

    def synchronize(self) -> None:
        while True:
            time.sleep(1)
            if self.loop:
                self.l_time.setText(get_time(self.sync_time))
                self.sync_time += 1





