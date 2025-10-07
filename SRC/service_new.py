import os
import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from yadisk import YaDisk

class RealTimeYandexDiskSync:
    def __init__(self, window, logger, configure, language):
        self.window = window
        self.logger = logger
        self.config = configure
        self.language = language

        self.disk = YaDisk(token=self.config['token'])
        self.local_folder = Path(self.config['local']).resolve()
        self.remote_folder = self.config['yddir'].strip('/')
        self.is_running = False

        # Очередь для обработки событий
        self.event_queue = []
        self.queue_lock = threading.Lock()
        self.processing = False

        # Трекеры изменений
        self.local_observer = None
        self.remote_poll_thread = None

        # Блокировки для предотвращения циклических синхронизаций
        self.sync_in_progress = False
        self.last_remote_check = 0
        self.remote_check_interval = 10  # секунды

        # Создаем локальную папку если не существует
        self.local_folder.mkdir(parents=True, exist_ok=True)

    def check_token(self):
        """Проверка валидности токена"""
        try:
            return self.disk.check_token()
        except Exception as e:
            self.logger.error(f"Ошибка проверки токена: {e}")
            return False

    class LocalFileHandler(FileSystemEventHandler):
        def __init__(self, sync_manager):
            self.sync_manager = sync_manager

        def on_created(self, event):
            if not event.is_directory:
                self.sync_manager.handle_local_event('created', event.src_path)

        def on_modified(self, event):
            if not event.is_directory:
                self.sync_manager.handle_local_event('modified', event.src_path)

        def on_deleted(self, event):
            if not event.is_directory:
                self.sync_manager.handle_local_event('deleted', event.src_path)

        def on_moved(self, event):
            if not event.is_directory:
                self.sync_manager.handle_local_event('moved', event.src_path, event.dest_path)

    def handle_local_event(self, event_type, src_path, dest_path=None):
        """Обработка локальных событий файловой системы"""
        if self.sync_in_progress:
            return

        try:
            local_path = Path(src_path)
            if not local_path.is_relative_to(self.local_folder):
                return

            relative_path = local_path.relative_to(self.local_folder)

            with self.queue_lock:
                self.event_queue.append({
                    'type': event_type,
                    'src_path': str(relative_path),
                    'dest_path': str(Path(dest_path).relative_to(self.local_folder)) if dest_path else None,
                    'timestamp': time.time(),
                    'source': 'local'
                })

            self.logger.debug(f"Локальное событие: {event_type} - {relative_path}")

        except Exception as e:
            self.logger.error(f"Ошибка обработки локального события: {e}")

    def monitor_remote_changes(self):
        """Мониторинг изменений на Yandex.Disk"""
        last_remote_state = {}

        while self.is_running:
            try:
                current_time = time.time()
                if current_time - self.last_remote_check >= self.remote_check_interval:
                    self.last_remote_check = current_time

                    current_remote_state = {}
                    for item in self.disk.listdir(self.remote_folder):
                        if item['type'] == 'file':
                            current_remote_state[item['name']] = {
                                'size': item['size'],
                                'modified': item['modified']
                            }

                    # Обнаружение новых файлов
                    for filename in current_remote_state:
                        if filename not in last_remote_state:
                            with self.queue_lock:
                                self.event_queue.append({
                                    'type': 'created',
                                    'src_path': filename,
                                    'timestamp': time.time(),
                                    'source': 'remote'
                                })
                            self.logger.debug(f"Обнаружен новый файл на Yandex.Disk: {filename}")

                    # Обнаружение удаленных файлов
                    for filename in last_remote_state:
                        if filename not in current_remote_state:
                            with self.queue_lock:
                                self.event_queue.append({
                                    'type': 'deleted',
                                    'src_path': filename,
                                    'timestamp': time.time(),
                                    'source': 'remote'
                                })
                            self.logger.debug(f"Обнаружено удаление на Yandex.Disk: {filename}")

                    last_remote_state = current_remote_state

            except Exception as e:
                self.logger.error(f"Ошибка мониторинга Yandex.Disk: {e}")

            time.sleep(5)

    def process_event_queue(self):
        """Обработка очереди событий"""
        while self.is_running:
            try:
                with self.queue_lock:
                    if not self.event_queue:
                        time.sleep(0.1)
                        continue

                    event = self.event_queue.pop(0)

                self.sync_in_progress = True

                if event['source'] == 'local':
                    self.handle_local_sync_event(event)
                else:
                    self.handle_remote_sync_event(event)

                self.sync_in_progress = False

            except Exception as e:
                self.logger.error(f"Ошибка обработки события: {e}")
                self.sync_in_progress = False
                time.sleep(1)

    def handle_local_sync_event(self, event):
        """Обработка событий от локальной файловой системы"""
        try:
            if event['type'] in ['created', 'modified']:
                local_path = self.local_folder / event['src_path']
                if local_path.exists():
                    self.upload_file(event['src_path'])

            elif event['type'] == 'deleted':
                self.delete_remote_file(event['src_path'])

            elif event['type'] == 'moved':
                # Удаляем старый файл и загружаем новый
                self.delete_remote_file(event['src_path'])
                if event['dest_path']:
                    self.upload_file(event['dest_path'])

        except Exception as e:
            self.logger.error(f"Ошибка обработки локального события синхронизации: {e}")

    def handle_remote_sync_event(self, event):
        """Обработка событий от Yandex.Disk"""
        try:
            if event['type'] == 'created':
                self.download_file(event['src_path'])

            elif event['type'] == 'deleted':
                local_path = self.local_folder / event['src_path']
                if local_path.exists():
                    local_path.unlink()
                    self.logger.info(f"Удален локальный файл: {event['src_path']}")

        except Exception as e:
            self.logger.error(f"Ошибка обработки удаленного события синхронизации: {e}")

    def upload_file(self, relative_path):
        """Загрузка файла на Yandex.Disk"""
        try:
            local_path = self.local_folder / relative_path
            remote_path = f"{self.remote_folder}/{relative_path}".replace('\\', '/')

            # Создаем папки на Yandex.Disk если нужно
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and not self.disk.exists(remote_dir):
                self.disk.mkdir(remote_dir)

            self.disk.upload(str(local_path), remote_path)
            self.logger.info(f"Загружен на Yandex.Disk: {relative_path}")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка загрузки {relative_path}: {e}")
            return False

    def download_file(self, relative_path):
        """Скачивание файла с Yandex.Disk"""
        try:
            remote_path = f"{self.remote_folder}/{relative_path}"
            local_path = self.local_folder / relative_path

            # Создаем локальные папки если нужно
            local_path.parent.mkdir(parents=True, exist_ok=True)

            self.disk.download(remote_path, str(local_path))
            self.logger.info(f"Скачан с Yandex.Disk: {relative_path}")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка скачивания {relative_path}: {e}")
            return False

    def delete_remote_file(self, relative_path):
        """Удаление файла с Yandex.Disk"""
        try:
            remote_path = f"{self.remote_folder}/{relative_path}"
            if self.disk.exists(remote_path):
                self.disk.remove(remote_path, permanently=True)
                self.logger.info(f"Удален с Yandex.Disk: {relative_path}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка удаления {relative_path}: {e}")
            return False

    def initial_sync(self):
        """Первоначальная синхронизация"""
        self.logger.info("Запуск первоначальной синхронизации...")

        try:
            # Создаем папку на Yandex.Disk если не существует
            if not self.disk.exists(self.remote_folder):
                self.disk.mkdir(self.remote_folder)

            # Скачиваем файлы с Yandex.Disk
            for item in self.disk.listdir(self.remote_folder):
                if item['type'] == 'file':
                    local_path = self.local_folder / item['name']
                    if not local_path.exists():
                        self.download_file(item['name'])

            # Загружаем локальные файлы
            for local_file in self.local_folder.rglob('*'):
                if local_file.is_file():
                    relative_path = local_file.relative_to(self.local_folder)
                    remote_path = f"{self.remote_folder}/{relative_path}"
                    if not self.disk.exists(remote_path):
                        self.upload_file(str(relative_path))

            self.logger.info("Первоначальная синхронизация завершена")

        except Exception as e:
            self.logger.error(f"Ошибка первоначальной синхронизации: {e}")

    def start_sync(self):
        """Запуск синхронизации в реальном времени"""
        if not self.check_token():
            self.logger.error("Неверный OAuth токен")
            return False

        self.is_running = True

        # Первоначальная синхронизация
        self.initial_sync()

        # Запуск мониторинга локальной файловой системы
        event_handler = self.LocalFileHandler(self)
        self.local_observer = Observer()
        self.local_observer.schedule(event_handler, str(self.local_folder), recursive=True)
        self.local_observer.start()

        # Запуск мониторинга Yandex.Disk
        self.remote_poll_thread = threading.Thread(target=self.monitor_remote_changes, daemon=True)
        self.remote_poll_thread.start()

        # Запуск обработки очереди событий
        self.processor_thread = threading.Thread(target=self.process_event_queue, daemon=True)
        self.processor_thread.start()

        self.logger.info("Синхронизатор в реальном времени запущен")
        return True

    def stop_sync(self):
        """Остановка синхронизации"""
        self.is_running = False

        if self.local_observer:
            self.local_observer.stop()
            self.local_observer.join()

        if self.remote_poll_thread and self.remote_poll_thread.is_alive():
            self.remote_poll_thread.join(timeout=5)

        if self.processor_thread and self.processor_thread.is_alive():
            self.processor_thread.join(timeout=5)

        self.logger.info("Синхронизатор остановлен")
