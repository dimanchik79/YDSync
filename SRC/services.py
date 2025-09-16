import os
import time
import threading
from pathlib import Path
from datetime import datetime

import yadisk
from watchdog.events import FileSystemEventHandler

class YandexDiskSync:
    """Класс для синхронизации с Яндекс.Диском"""

    def __init__(self, window, logger, configure: dict, language: dict):
        self.window = window
        self.logger = logger
        self.configure = configure
        self.language = language

        self.local_folder = Path(self.configure['local'])
        
        self.cloud_folder = self.configure['yddir']
        self.token = self.configure['token']

        # Создаем локальную папку если не существует
        self.local_folder.mkdir(parents=True, exist_ok=True)

        # Инициализируем клиент Яндекс.Диска
        self.y = yadisk.YaDisk(token=self.token)

        # Проверяем подключение
        if not self.y.check_token():
            self.logger.error("Неверный токен Яндекс.Диска!")
            raise ValueError("Invalid Yandex.Disk token")

        # Создаем папку в облаке если не существует
        if not self.y.exists(self.configure['yddir']):
            self.y.mkdir(self.configure['yddir'])

        self.sync_lock = threading.Lock()
        self.running = False

    def is_ignored(self, path: Path) -> bool:
        """Проверяет, нужно ли игнорировать файл/папку"""
        if path.name.startswith('.'):
            return True

        # Проверка расширений
        if path.suffix.lower() in self.configure['ignoreextensions']:
            return True

        return False

    def upload_file(self, local_path: Path):
        """Загружает файл в облако"""
        try:
            if self.is_ignored(local_path):
                return

            relative_path = local_path.relative_to(self.local_folder)
            target_cloud_path = f"{self.cloud_folder}/{relative_path}"

            # Создаем родительские папки в облаке
            parent_dir = os.path.dirname(target_cloud_path)
            if not self.y.exists(parent_dir):
                self.y.mkdir(parent_dir)

            self.y.upload(str(local_path), target_cloud_path, overwrite=True)
            self.logger.info(f"Загружен: {local_path} -> {target_cloud_path}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки {local_path}: {e}")

    def download_file(self, cloud_path: str, local_path: Path):
        """Скачивает файл из облака"""
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            self.y.download(cloud_path, str(local_path))
            self.logger.info(f"Скачан: {cloud_path} -> {local_path}")

        except Exception as e:
            self.logger.error(f"Ошибка скачивания {cloud_path}: {e}")

    def delete_cloud_file(self, cloud_path: str):
        """Удаляет файл из облака"""
        try:
            self.y.remove(cloud_path)
            self.logger.info(f"Удален из облака: {cloud_path}")
        except Exception as e:
            self.logger.error(f"Ошибка удаления из облака {cloud_path}: {e}")

    def delete_local_file(self, local_path: Path):
        """Удаляет локальный файл"""
        try:
            if local_path.exists():
                if local_path.is_file():
                    local_path.unlink()
                else:
                    import shutil
                    shutil.rmtree(local_path)
                self.logger.info(f"Удален локально: {local_path}")
        except Exception as e:
            self.logger.error(f"Ошибка удаления локального файла {local_path}: {e}")

    def sync_local_to_cloud(self):
        """Синхронизация локальных изменений в облако"""
        with self.sync_lock:
            try:
                # Рекурсивно обходим локальную папку
                for root, dirs, files in os.walk(self.local_folder):
                    root_path = Path(root)

                    # Пропускаем игнорируемые папки
                    dirs[:] = [d for d in dirs if not self.is_ignored(root_path / d)]

                    for file in files:
                        local_file = root_path / file
                        if not self.is_ignored(local_file):
                            self.upload_file(local_file)

                self.logger.info("Синхронизация лок->облако завершена")
            except Exception as e:
                self.logger.error(f"Ошибка синхронизации лок->облако: {e}")

    def sync_cloud_to_local(self):
        """Синхронизация облачных изменений на локальный диск"""
        with self.sync_lock:
            try:
                # Получаем список файлов в облаке
                cloud_files = {}
                for item in self.y.listdir(self.cloud_folder, recursive=True):
                    if not str(item.path).endswith('/'):  # Это файл, а не папка
                        cloud_files[item.path] = item.modified

                # Скачиваем новые/измененные файлы
                for cloud_path, cloud_mtime in cloud_files.items():
                    relative_path = cloud_path[len(self.cloud_folder) + 1:]
                    local_path = self.local_folder / relative_path

                    need_download = False

                    if not local_path.exists():
                        need_download = True
                    else:
                        # Сравниваем время модификации
                        local_mtime = datetime.fromtimestamp(local_path.stat().st_mtime)
                        cloud_mtime_dt = datetime.strptime(cloud_mtime, '%Y-%m-%dT%H:%M:%S%z')

                        if cloud_mtime_dt > local_mtime.replace(tzinfo=cloud_mtime_dt.tzinfo):
                            need_download = True

                    if need_download and not self.is_ignored(local_path):
                        self.download_file(cloud_path, local_path)

                # Удаляем локальные файлы, которых нет в облаке
                for local_path in self.local_folder.rglob('*'):
                    if local_path.is_file() and not self.is_ignored(local_path):
                        relative_path = local_path.relative_to(self.local_folder)
                        cloud_path = f"{self.cloud_folder}/{relative_path}"

                        if not self.y.exists(cloud_path):
                            self.delete_local_file(local_path)

                self.logger.info("Синхронизация облако->лок завершена")
            except Exception as e:
                self.logger.error(f"Ошибка синхронизации облако->лок: {e}")

    def full_sync(self):
        """Полная двусторонняя синхронизация"""
        self.logger.info("Запуск полной синхронизации...")
        self.sync_local_to_cloud()
        self.sync_cloud_to_local()
        self.logger.info("Полная синхронизация завершена")


class FileChangeHandler(FileSystemEventHandler):
    """Обработчик изменений файловой системы"""

    def __init__(self, window, sync_service, logger):
        super().__init__()
        self.window = window
        self.logger = logger
        self.sync_service = sync_service
        self.debounce_timer = None
        self.debounce_time = 2  # секунды

    def on_any_event(self, event):
        """Обрабатывает любое изменение файловой системы"""
        if event.is_directory:
            return

        src_path = Path(str(event.src_path))
        if self.sync_service.is_ignored(src_path):
            return

        # Откладываем синхронизацию для избежания множественных вызовов
        if self.debounce_timer:
            self.debounce_timer.cancel()

        self.debounce_timer = threading.Timer(self.debounce_time, self.trigger_sync)
        self.debounce_timer.start()

    def trigger_sync(self):
        """Запускает синхронизацию после задержки"""
        try:
            self.sync_service.sync_local_to_cloud()
        except Exception as e:
            self.logger.error(f"Ошибка в обработчике изменений: {e}")
