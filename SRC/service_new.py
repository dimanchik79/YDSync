import os
import time
import threading
import hashlib
from pathlib import Path
from collections import deque
from datetime import datetime
from typing import Dict, Optional, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from yadisk import YaDisk

class TwoWayYandexDiskSync:
    """Двухсторонняя синхронизация с Яндекс.Диском"""
    
    def __init__(self, window, logger, configure, language):
        self.window = window
        self.logger = logger
        self.config = configure
        self.language = language
        
        # Инициализация API
        self.disk = YaDisk(token=self.config['token'])
        self.local_root = Path(self.config['local']).resolve()
        self.remote_root = self.config['yddir'].strip('/')
        
        # Состояние синхронизатора
        self.is_running = False
        self.stop_event = threading.Event()
        
        # Очередь событий
        self.event_queue = deque()
        self.queue_lock = threading.Lock()
        
        # Блокировка для предотвращения циклов
        self.sync_lock = threading.Lock()
        self.syncing = False
        
        # Кэш состояния удалённых файлов
        self.remote_state_cache: Dict[str, dict] = {}
        self.cache_lock = threading.Lock()
        
        # Интервалы
        self.poll_interval = 5  # секунды для опроса Яндекс.Диска
        
        # Потоки
        self.local_observer = None
        self.remote_monitor_thread = None
        self.queue_processor_thread = None
        
        # Создаём локальную папку
        self.local_root.mkdir(parents=True, exist_ok=True)
        
    # ============================================================
    #  Базовые операции с Яндекс.Диском
    # ============================================================
    
    def check_token(self) -> bool:
        """Проверка валидности токена"""
        try:
            return self.disk.check_token()
        except Exception as e:
            self.logger.error(f"Toke verify error: {e}")
            return False
    
    def _get_remote_path(self, relative_path: str) -> str:
        """Получить полный путь на Яндекс.Диске"""
        return f"{self.remote_root}/{relative_path}".replace('\\', '/')
    
    def _get_remote_info(self, relative_path: str) -> Optional[dict]:
        """Получить информацию о файле на Яндекс.Диске"""
        try:
            remote_path = self._get_remote_path(relative_path)
            if self.disk.exists(remote_path):
                info = self.disk.get_meta(remote_path)
                return {
                    'size': info['size'],
                    'modified': info['modified'],
                    'etag': info.get('etag', ''),
                    'type': info['type']
                }
        except Exception as e:
            self.logger.debug(f"Ошибка получения информации о {relative_path}: {e}")
        return None
    
    def _get_local_info(self, relative_path: str) -> Optional[dict]:
        """Получить информацию о локальном файле"""
        local_path = self.local_root / relative_path
        if local_path.exists() and local_path.is_file():
            stat = local_path.stat()
            return {
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'type': 'file'
            }
        return None
    
    def _compute_md5(self, file_path: Path) -> str:
        """Вычисление MD5 хеша файла"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    # ============================================================
    #  Синхронизация файлов и папок
    # ============================================================
    
    def upload_file(self, relative_path: str) -> bool:
        """Загрузить файл на Яндекс.Диск"""
        try:
            local_path = self.local_root / relative_path
            if not local_path.exists():
                return False
            
            remote_path = self._get_remote_path(relative_path)
            
            # Создаём удалённые папки
            remote_dir = os.path.dirname(remote_path)
            if remote_dir and not self.disk.exists(remote_dir):
                self.disk.mkdir(remote_dir)
            
            # Загружаем файл с перезаписью
            self.disk.upload(str(local_path), remote_path, overwrite=True)
            self.logger.info(f"[UPLOAD]: {relative_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Upload error {relative_path}: {e}")
            return False
    
    def download_file(self, relative_path: str) -> bool:
        """Скачать файл с Яндекс.Диска"""
        try:
            remote_path = self._get_remote_path(relative_path)
            local_path = self.local_root / relative_path
            
            # Создаём локальные папки
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Скачиваем файл с перезаписью
            self.disk.download(remote_path, str(local_path), overwrite=True)
            self.logger.info(f"[DOWNLOAD]: {relative_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Download error {relative_path}: {e}")
            return False
    
    def delete_remote(self, relative_path: str, is_dir: bool = False) -> bool:
        """Удалить файл/папку на Яндекс.Диске"""
        try:
            remote_path = self._get_remote_path(relative_path)
            if self.disk.exists(remote_path):
                self.disk.remove(remote_path, permanently=True)
                self.logger.info(f"[DELETE] on Yandex.Disk: {relative_path}")
            return True
        except Exception as e:
            self.logger.error(f"Delete error {relative_path}: {e}")
            return False
    
    def delete_local(self, relative_path: str) -> bool:
        """Удалить локальный файл/папку"""
        try:
            local_path = self.local_root / relative_path
            if local_path.exists():
                if local_path.is_dir():
                    import shutil
                    shutil.rmtree(local_path)
                else:
                    local_path.unlink()
                self.logger.info(f"[DELETE] local: {relative_path}")
            return True
        except Exception as e:
            self.logger.error(f"Local delele error {relative_path}: {e}")
            return False
    
    def move_remote(self, old_path: str, new_path: str) -> bool:
        """Переместить файл на Яндекс.Диске"""
        try:
            old_remote = self._get_remote_path(old_path)
            new_remote = self._get_remote_path(new_path)
            
            # Создаём целевую папку
            new_dir = os.path.dirname(new_remote)
            if new_dir and not self.disk.exists(new_dir):
                self.disk.mkdir(new_dir)
            
            self.disk.move(old_remote, new_remote)
            self.logger.info(f"[MOVE] Yandex.Disk: {old_path} -> {new_path}")
            return True
        except Exception as e:
            self.logger.error(f"Move error {old_path} -> {new_path}: {e}")
            return False
    
    def move_local(self, old_path: str, new_path: str) -> bool:
        """Переместить локальный файл"""
        try:
            old_local = self.local_root / old_path
            new_local = self.local_root / new_path
            
            # Создаём целевую папку
            new_local.parent.mkdir(parents=True, exist_ok=True)
            
            old_local.rename(new_local)
            self.logger.info(f"[MOVE] local: {old_path} -> {new_path}")
            return True
        except Exception as e:
            self.logger.error(f"Local move error: {e}")
            return False
    
    # ============================================================
    #  Сбор состояния файлов
    # ============================================================
    
    def _scan_local_files(self) -> Dict[str, dict]:
        """Сканирование всех локальных файлов"""
        files = {}
        for file_path in self.local_root.rglob('*'):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(self.local_root))
                stat = file_path.stat()
                files[rel_path] = {
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'type': 'file'
                }
        return files
    
    def _scan_remote_files(self) -> Dict[str, dict]:
        """Сканирование всех удалённых файлов (рекурсивно)"""
        files = {}
        
        def scan(remote_path: str, base_path: str = ''):
            try:
                for item in self.disk.listdir(remote_path):
                    item_path = item['path']
                    # Извлекаем относительный путь
                    rel = self._extract_relative_path(item_path)
                    
                    if item['type'] == 'file':
                        files[rel] = {
                            'size': item['size'],
                            'modified': item['modified'],
                            'type': 'file'
                        }
                    elif item['type'] == 'dir':
                        scan(item_path, rel)
            except Exception as e:
                self.logger.error(f"Scan ERROR {remote_path}: {e}")
        
        try:
            if self.disk.exists(self.remote_root):
                scan(self.remote_root)
        except Exception as e:
            self.logger.error(f"Romote file SCAN Error: {e}")
        
        return files
    
    def _extract_relative_path(self, full_path: str) -> str:
        """Извлечение относительного пути из полного пути Яндекс.Диска"""
        # Убираем 'disk:'
        if full_path.startswith('disk:'):
            full_path = full_path[5:]
        full_path = full_path.lstrip('/\\')
        
        # Находим часть после remote_root
        try:
            path = Path(full_path)
            rel = path.relative_to(self.remote_root)
            return str(rel).replace('\\', '/')
        except ValueError:
            return full_path.replace('\\', '/')
    
    # ============================================================
    #  Синхронизация
    # ============================================================
    
    def _determine_action(self, local_info: Optional[dict], 
                         remote_info: Optional[dict]) -> Tuple[str, Optional[str]]:
        """
        Определяет, какое действие нужно выполнить.
        Возвращает (action, reason)
        action: 'upload', 'download', 'delete_local', 'delete_remote', 'none'
        """
        # Только локальный
        if local_info and not remote_info:
            return ('upload', 'только локально')
        
        # Только удалённый
        if not local_info and remote_info:
            return ('download', 'только на диске')
        
        # Нет нигде
        if not local_info and not remote_info:
            return ('none', '')
        
        # Есть везде - сравниваем
        if local_info and remote_info:
            # Сравниваем размер и дату
            if local_info['size'] != remote_info['size']:
                # Определяем, что новее
                if local_info['modified'] > remote_info['modified']:
                    return ('upload', 'локальная версия новее')
                else:
                    return ('download', 'удалённая версия новее')
            
            # Для папок возвращаем none
            if local_info.get('type') == 'dir' or remote_info.get('type') == 'dir':
                return ('none', '')
        
        return ('none', 'синхронизировано')
    
    def sync_file(self, relative_path: str, local_info: Optional[dict], 
                  remote_info: Optional[dict]) -> bool:
        """Синхронизирует один файл"""
        action, reason = self._determine_action(local_info, remote_info)
        
        if action == 'none':
            return True
        
        self.logger.debug(f"Synhronize {relative_path}: {action} ({reason})")
        
        if action == 'upload':
            return self.upload_file(relative_path)
        elif action == 'download':
            return self.download_file(relative_path)
        elif action == 'delete_local':
            return self.delete_local(relative_path)
        elif action == 'delete_remote':
            return self.delete_remote(relative_path)
        
        return False
    
    def full_sync(self) -> bool:
        """Полная синхронизация всех файлов"""
        self.logger.info("[SYNC] Full synhronize begin...")
        
        with self.sync_lock:
            self.syncing = True
            try:
                # Сканируем обе стороны
                local_files = self._scan_local_files()
                remote_files = self._scan_remote_files()
                
                # Синхронизируем все файлы
                all_paths = set(local_files.keys()) | set(remote_files.keys())
                
                synced = 0
                for path in all_paths:
                    if self.sync_file(path, 
                                     local_files.get(path), 
                                     remote_files.get(path)):
                        synced += 1
                
                self.logger.info(f"[SYNC] Full sync end ({synced} files)")
                
                # Обновляем кэш
                with self.cache_lock:
                    self.remote_state_cache = remote_files.copy()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Full synhronize Error: {e}")
                return False
            finally:
                self.syncing = False
    
    # ============================================================
    #  Обработка событий
    # ============================================================
    
    class LocalEventHandler(FileSystemEventHandler):
        def __init__(self, sync_manager):
            self.sync_manager = sync_manager
        
        def on_created(self, event):
            if self.sync_manager.syncing:
                return
            if not event.is_directory:
                self.sync_manager._queue_event('created', event.src_path)
        
        def on_modified(self, event):
            if self.sync_manager.syncing:
                return
            if not event.is_directory:
                self.sync_manager._queue_event('modified', event.src_path)
        
        def on_deleted(self, event):
            if self.sync_manager.syncing:
                return
            if not event.is_directory:
                self.sync_manager._queue_event('deleted', event.src_path)
        
        def on_moved(self, event):
            if self.sync_manager.syncing:
                return
            if not event.is_directory:
                self.sync_manager._queue_event('moved', event.src_path, event.dest_path)
    
    def _queue_event(self, event_type: str, src: str, dest: str = None):
        """Добавить событие в очередь"""
        try:
            src_path = Path(src)
            if not src_path.is_relative_to(self.local_root):
                return
            
            rel_src = str(src_path.relative_to(self.local_root))
            rel_dest = None
            
            if dest:
                dest_path = Path(dest)
                if dest_path.is_relative_to(self.local_root):
                    rel_dest = str(dest_path.relative_to(self.local_root))
            
            with self.queue_lock:
                self.event_queue.append({
                    'type': event_type,
                    'src': rel_src,
                    'dest': rel_dest,
                    'time': time.time()
                })
            
            self.logger.debug(f"Task in quelle: {event_type} - {rel_src}")
            
        except Exception as e:
            self.logger.error(f"Qwuelle Error: {e}")
    
    def _process_events(self):
        """Обработка очереди событий"""
        while not self.stop_event.is_set() and self.is_running:
            try:
                with self.queue_lock:
                    if not self.event_queue:
                        time.sleep(0.1)
                        continue
                    event = self.event_queue.popleft()
                
                with self.sync_lock:
                    self._handle_event(event)
                    
            except Exception as e:
                self.logger.error(f"Quelle ERROR: {e}")
                time.sleep(1)
    
    def _handle_event(self, event: dict):
        """Обработка одного события"""
        event_type = event['type']
        src = event['src']
        dest = event.get('dest')
        
        if event_type == 'created':
            # Проверяем, нет ли уже такого файла на диске
            remote_info = self._get_remote_info(src)
            if remote_info:
                # Сравниваем, что новее
                local_info = self._get_local_info(src)
                if local_info and local_info['modified'] > remote_info['modified']:
                    self.upload_file(src)
            else:
                self.upload_file(src)
                
        elif event_type == 'modified':
            # Загружаем изменённый файл
            self.upload_file(src)
            
        elif event_type == 'deleted':
            # Удаляем на диске
            self.delete_remote(src)
            
        elif event_type == 'moved' and dest:
            # Перемещаем на диске
            self.move_remote(src, dest)
    
    def _monitor_remote(self):
        """Мониторинг удалённых изменений"""
        last_state = {}
        
        while not self.stop_event.is_set() and self.is_running:
            try:
                time.sleep(self.poll_interval)
                
                if self.syncing:
                    continue
                
                # Сканируем текущее состояние
                current_state = self._scan_remote_files()
                
                # Находим изменения
                all_paths = set(last_state.keys()) | set(current_state.keys())
                
                for path in all_paths:
                    if self.syncing:
                        break
                    
                    last = last_state.get(path)
                    current = current_state.get(path)
                    
                    # Файл удалён
                    if last and not current:
                        self._queue_remote_change('deleted', path)
                    
                    # Файл создан
                    elif not last and current:
                        self._queue_remote_change('created', path)
                    
                    # Файл изменён
                    elif last and current:
                        if (last['size'] != current['size'] or 
                            last['modified'] != current['modified']):
                            self._queue_remote_change('modified', path)
                
                last_state = current_state
                
            except Exception as e:
                self.logger.error(f"Ошибка мониторинга удалённых файлов: {e}")
    
    def _queue_remote_change(self, change_type: str, path: str):
        """Обработка удалённых изменений"""
        if self.syncing:
            return
        
        with self.sync_lock:
            if change_type == 'created':
                # Скачиваем новый файл
                local_info = self._get_local_info(path)
                if not local_info:
                    self.download_file(path)
                else:
                    # Сравниваем, что новее
                    remote_info = self._get_remote_info(path)
                    if remote_info and remote_info['modified'] > local_info['modified']:
                        self.download_file(path)
                    else:
                        self.upload_file(path)
                        
            elif change_type == 'deleted':
                # Удаляем локальный файл
                self.delete_local(path)
                
            elif change_type == 'modified':
                # Скачиваем обновлённый файл
                self.download_file(path)
    
    # ============================================================
    #  Управление синхронизацией
    # ============================================================
    
    def start_sync(self) -> bool:
        """Запуск синхронизации"""
        if not self.check_token():
            msg = self.language.get('token_error', {}).get(self.config['language'], 'Ошибка токена')
            self.logger.error(msg)
            if self.window:
                self.window.l_prompt.setText(msg)
            return False
        
        if self.is_running:
            self.logger.warning("Sync starting now...")
            return False
        
        self.is_running = True
        self.stop_event.clear()
        
        # Полная синхронизация при запуске
        self.full_sync()
        
        # Запуск локального мониторинга
        event_handler = self.LocalEventHandler(self)
        self.local_observer = Observer()
        self.local_observer.schedule(event_handler, str(self.local_root), recursive=True)
        self.local_observer.start()
        
        # Запуск удалённого мониторинга
        self.remote_monitor_thread = threading.Thread(target=self._monitor_remote, daemon=True)
        self.remote_monitor_thread.start()
        
        # Запуск обработчика очереди
        self.queue_processor_thread = threading.Thread(target=self._process_events, daemon=True)
        self.queue_processor_thread.start()
        
        msg = self.language.get('sync_start', {}).get(self.config['language'], 'Синхронизация запущена')
        self.logger.info(msg)
        if self.window:
            self.window.l_prompt.setText(msg)
        
        return True
    
    def stop_sync(self):
        """Остановка синхронизации"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.stop_event.set()
        
        # Останавливаем локальный наблюдатель
        if self.local_observer:
            self.local_observer.stop()
            self.local_observer.join(timeout=2)
        
        # Ждём завершения потоков
        if self.remote_monitor_thread and self.remote_monitor_thread.is_alive():
            self.remote_monitor_thread.join(timeout=2)
        
        if self.queue_processor_thread and self.queue_processor_thread.is_alive():
            self.queue_processor_thread.join(timeout=2)
        
        # Очищаем очередь
        with self.queue_lock:
            self.event_queue.clear()
        
        msg = self.language.get('sync_end', {}).get(self.config['language'], 'Синхронизация остановлена')
        self.logger.info(msg)
        if self.window:
            self.window.l_prompt.setText(msg)
    
    def force_resync(self):
        """Принудительная полная синхронизация"""
        self.full_sync()