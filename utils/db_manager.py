import sqlite3
import json
import os
import shutil
from datetime import datetime
from utils.logger import logger


class DBManager:
    """
    Отказоустойчивое хранилище данных.
    Реализует паттерны: Integrity Guard (контроль целостности) и
    Outbox (очередь сообщений для внешних сервисов).
    """

    def __init__(self, db_path="aiko_data.db"):
        self.db_path = db_path
        self.is_functional = False
        self.was_recovered = False
        self.on_error_callback = None
        self._init_db()

    def _init_db(self):
        """Проверка физического состояния и инициализация схем."""
        conn = None
        try:
            if os.path.exists(self.db_path):
                # Открываем соединение без контекстного менеджера для ручного контроля
                conn = sqlite3.connect(self.db_path)
                res = conn.execute("PRAGMA integrity_check").fetchone()
                if res[0] != "ok":
                    raise sqlite3.DatabaseError("Integrity check failed")

                conn.execute("PRAGMA journal_mode=WAL")
                conn.close()  # Закрываем перед основной стадией

            self._create_tables()
            self.is_functional = True
            logger.info("DB: Система запущена в штатном режиме (WAL enabled).")
        except (sqlite3.DatabaseError, sqlite3.OperationalError) as e:
            logger.error(f"DB: Обнаружено повреждение базы: {e}")
            if conn:
                try:
                    conn.close()
                except:
                    pass
            self._handle_corruption()

    def _handle_corruption(self):
        """Изоляция поврежденного файла и горячая замена (AK-SYS-02)."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.corrupt_{timestamp}"
        try:
            if os.path.exists(self.db_path):
                shutil.move(self.db_path, backup_path)
                logger.warning(f"DB: Поврежденный файл изолирован -> {backup_path}")

            self._create_tables()
            self.is_functional, self.was_recovered = True, True
            logger.info("DB: Развернута чистая структура таблиц.")
        except Exception as e:
            self.is_functional = False
            logger.critical(f"DB: Фатальный сбой ФС при восстановлении: {e}")

    def _create_tables(self):
        """Создание схемы данных с индексами."""
        with sqlite3.connect(self.db_path) as conn:
            # Настройка режима для КАЖДОГО нового подключения или создания
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")  # Оптимально для WAL

            # Планировщик задач + ИНДЕКС
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    payload TEXT,
                    exec_at DATETIME,
                    status TEXT DEFAULT 'pending'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sch_pending ON scheduler(status, exec_at)")

            # KV Store
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Outbox + ИНДЕКС
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tg_outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    created_at DATETIME,
                    status TEXT DEFAULT 'pending'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tg_pending ON tg_outbox(status, priority DESC)")
            conn.commit()

    # --- SHARED HELPERS ---

    def _report_runtime_error(self, error):
        msg = f"Runtime DB Error: {error}"
        logger.error(msg, exc_info=True)
        if self.on_error_callback:
            self.on_error_callback(msg)

    def _to_json(self, data):
        return json.dumps(data, ensure_ascii=False) if isinstance(data, (dict, list)) else data

    # --- SCHEDULER ---

    def add_task(self, task_type, payload, exec_at):
        if not self.is_functional: return False
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO scheduler (type, payload, exec_at) VALUES (?, ?, ?)",
                    (task_type, self._to_json(payload), exec_at)
                )
            return True
        except Exception as e:
            self._report_runtime_error(e);
            return False

    def get_pending_tasks(self):
        if not self.is_functional: return []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with sqlite3.connect(self.db_path, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, type, payload FROM scheduler WHERE exec_at <= ? AND status = 'pending'",
                    (now,)
                )
                return cursor.fetchall()
        except Exception as e:
            self._report_runtime_error(e);
            return []

    def update_task_status(self, task_id, status='done'):
        if not self.is_functional: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("UPDATE scheduler SET status = ? WHERE id = ?", (status, task_id))
        except Exception as e:
            self._report_runtime_error(e)

    # --- KV STORE ---

    def set_val(self, key, value):
        if not self.is_functional: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                             (key, self._to_json(value)))
        except Exception as e:
            self._report_runtime_error(e)

    def get_val(self, key, default=None):
        if not self.is_functional: return default
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
                if not row: return default

                raw_val = row[0]
                try:
                    return json.loads(raw_val)
                except (json.JSONDecodeError, TypeError):
                    return raw_val  # Если не JSON, возвращаем как есть
        except Exception as e:
            logger.error(f"DB KV Read error: {e}")
            return default

    # --- TELEGRAM OUTBOX ---

    def add_tg_message(self, text, priority=0):
        if not self.is_functional: return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO tg_outbox (message, priority, created_at) VALUES (?, ?, ?)",
                    (text, priority, now)
                )
            return True
        except Exception as e:
            logger.error(f"DB Outbox Error: {e}");
            return False

    def get_pending_tg_messages(self):
        if not self.is_functional: return []
        try:
            with sqlite3.connect(self.db_path) as conn:
                return conn.execute(
                    "SELECT id, message, created_at FROM tg_outbox WHERE status = 'pending' ORDER BY id ASC"
                ).fetchall()
        except Exception as e:
            logger.error(f"DB: Error reading TG queue: {e}");
            return []

    def mark_tg_sent(self, msg_id):
        """Удаляет сообщение или переводит в архив (Status Change)."""
        if not self.is_functional: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                # В твоей версии удаление — это ок для экономии места,
                # но для отладки лучше сменить статус
                conn.execute("DELETE FROM tg_outbox WHERE id = ?", (msg_id,))
        except Exception as e:
            logger.error(f"DB: Sent mark error: {e}")

    def delete_task(self, task_id):
        if not self.is_functional: return False
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM scheduler WHERE id = ?", (task_id,))
            return True
        except Exception as e:
            self._report_runtime_error(e);
            return False


# Глобальный инстанс
db = DBManager()