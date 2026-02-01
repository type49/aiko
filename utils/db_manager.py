import sqlite3
import json
from datetime import datetime


class DBManager:
    def __init__(self, db_path="aiko_data.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 1. ПЛАНИРОВЩИК (для всех типов отложенных задач)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scheduler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,        -- 'reminder', 'system_update', 'focus_check'
                    payload TEXT,     -- Здесь будет JSON или текст
                    exec_at DATETIME,
                    status TEXT DEFAULT 'pending'
                )
            """)

            # 2. УНИВЕРСАЛЬНОЕ ХРАНИЛИЩЕ (для настроек, флагов, памяти Айко)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    # --- РАБОТА С ПЛАНИРОВЩИКОМ ---
    def add_task(self, task_type, payload, exec_at):
        """Универсальное добавление задачи"""
        try:
            # Если payload - словарь, превращаем в JSON строку
            if isinstance(payload, dict):
                payload = json.dumps(payload, ensure_ascii=False)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO scheduler (type, payload, exec_at) VALUES (?, ?, ?)",
                    (task_type, payload, exec_at)
                )
            return True
        except Exception as e:
            print(f"[DB ERROR]: Ошибка добавления задачи: {e}")
            return False

    def get_pending_tasks(self):
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
            print(f"[DB ERROR]: Ошибка получения задач: {e}")
            return []

    def update_task_status(self, task_id, status='done'):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE scheduler SET status = ? WHERE id = ?", (status, task_id))

    # --- РАБОТА С НАСТРОЙКАМИ (Key-Value) ---
    def set_val(self, key, value):
        """Сохранить любое значение (напр. режим фокуса, громкость)"""
        val_str = json.dumps(value, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, val_str))

    def get_val(self, key, default=None):
        """Получить значение по ключу"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
                row = cursor.fetchone()
                return json.loads(row[0]) if row else default
        except:
            return default


# Создаем глобальный объект для импорта
db = DBManager()