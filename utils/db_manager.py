import sqlite3
import json
import os
import shutil
from datetime import datetime
from utils.logger import logger


class DBManager:
    def __init__(self, db_path="aiko_data.db"):
        self.db_path = db_path
        self.is_functional = False
        self.was_recovered = False
        self.on_error_callback = None  # Сюда GUI подпишет функцию вывода HUD
        self._init_db()

    def _init_db(self):
        """Инициализация с проверкой целостности"""
        try:
            if os.path.exists(self.db_path):
                with sqlite3.connect(self.db_path) as conn:
                    # Проверка файла на физическое повреждение
                    res = conn.execute("PRAGMA integrity_check").fetchone()
                    if res[0] != "ok":
                        raise sqlite3.DatabaseError("Integrity check failed")

            self._create_tables()
            self.is_functional = True
            logger.info("БД: Система инициализирована корректно.")
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            logger.error(f"БД: Обнаружено повреждение при старте: {e}")
            self._handle_corruption()

    def _handle_corruption(self):
        """Изоляция битого файла и создание нового (Fix for AK-SYS-02)"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.corrupt_{timestamp}"
        try:
            if os.path.exists(self.db_path):
                shutil.move(self.db_path, backup_path)
                logger.warning(f"БД: Поврежденный файл перемещен в {backup_path}")

            self._create_tables()
            self.is_functional = True
            self.was_recovered = True
            logger.info("БД: Создана чистая база данных.")
        except Exception as e:
            self.is_functional = False
            logger.critical(f"БД: Тотальный сбой файловой системы: {e}")

    def _create_tables(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    payload TEXT,
                    exec_at DATETIME,
                    status TEXT DEFAULT 'pending'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def _report_runtime_error(self, error):
        """Оповещение системы о сбое в реальном времени (Fix for AK-SYS-04)"""
        msg = f"Критический сбой БД во время работы: {error}"
        logger.error(msg)
        if self.on_error_callback:
            self.on_error_callback(msg)
        self.is_functional = False

    # --- РАБОТА С ПЛАНИРОВЩИКОМ ---
    def add_task(self, task_type, payload, exec_at):
        if not self.is_functional: return False
        try:
            if isinstance(payload, dict):
                payload = json.dumps(payload, ensure_ascii=False)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO scheduler (type, payload, exec_at) VALUES (?, ?, ?)",
                    (task_type, payload, exec_at)
                )
            return True
        except Exception as e:
            self._report_runtime_error(e)
            return False

    def get_pending_tasks(self):
        if not self.is_functional: return []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, type, payload FROM scheduler WHERE exec_at <= ? AND status = 'pending'",
                    (now,)
                )
                return cursor.fetchall()
        except Exception as e:
            self._report_runtime_error(e)
            return []

    def update_task_status(self, task_id, status='done'):
        if not self.is_functional: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE scheduler SET status = ? WHERE id = ?", (status, task_id))
        except Exception as e:
            self._report_runtime_error(e)

    # --- KEY-VALUE STORE ---
    def set_val(self, key, value):
        if not self.is_functional: return
        try:
            val_str = json.dumps(value, ensure_ascii=False)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, val_str))
        except Exception as e:
            self._report_runtime_error(e)

    def get_val(self, key, default=None):
        if not self.is_functional: return default
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
                row = cursor.fetchone()
                return json.loads(row[0]) if row else default
        except Exception as e:
            # Здесь не репортим в HUD, чтобы не спамить при пустых запросах
            return default


db = DBManager()