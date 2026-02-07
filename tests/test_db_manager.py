"""
Тесты для DBManager
"""
import pytest
import json
from datetime import datetime, timedelta
from utils.db_manager import DBManager


@pytest.mark.unit
@pytest.mark.db
class TestDBManager:
    """Тесты менеджера базы данных"""
    
    def test_initialization(self, test_db):
        """Проверка инициализации БД"""
        assert test_db.is_functional is True
        assert test_db.was_recovered is False
    
    def test_add_task(self, test_db):
        """Проверка добавления задачи"""
        exec_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"message": "Test reminder"}
        
        result = test_db.add_task("reminder", payload, exec_time)
        assert result is True
    
    def test_get_pending_tasks_empty(self, test_db):
        """Проверка получения задач когда их нет"""
        tasks = test_db.get_pending_tasks()
        assert tasks == []
    
    def test_get_pending_tasks(self, test_db):
        """Проверка получения задач в очереди"""
        # Добавляем задачу в прошлом (должна вернуться)
        past_time = (datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        payload = {"text": "Past task"}
        test_db.add_task("reminder", payload, past_time)
        
        # Добавляем задачу в будущем (не должна вернуться)
        future_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        test_db.add_task("timer", {"text": "Future task"}, future_time)
        
        tasks = test_db.get_pending_tasks()
        assert len(tasks) == 1
        
        task_id, task_type, task_payload = tasks[0]
        assert task_type == "reminder"
        parsed = json.loads(task_payload)
        assert parsed["text"] == "Past task"
    
    def test_update_task_status(self, test_db):
        """Проверка обновления статуса задачи"""
        exec_time = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
        test_db.add_task("test", {"data": 1}, exec_time)
        
        tasks = test_db.get_pending_tasks()
        assert len(tasks) == 1
        
        task_id = tasks[0][0]
        test_db.update_task_status(task_id, "done")
        
        # Проверяем что задача больше не pending
        tasks_after = test_db.get_pending_tasks()
        assert len(tasks_after) == 0
    
    def test_delete_task(self, test_db):
        """Проверка удаления задачи"""
        exec_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_db.add_task("test", {}, exec_time)
        
        tasks = test_db.get_pending_tasks()
        task_id = tasks[0][0]
        
        result = test_db.delete_task(task_id)
        assert result is True
        
        tasks_after = test_db.get_pending_tasks()
        assert len(tasks_after) == 0
    
    def test_kv_store_set_get(self, test_db):
        """Проверка KV хранилища"""
        test_db.set_val("test_key", "test_value")
        value = test_db.get_val("test_key")
        assert value == "test_value"
    
    def test_kv_store_complex_value(self, test_db):
        """Проверка KV с сложными типами"""
        complex_data = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "number": 42
        }
        
        test_db.set_val("complex", complex_data)
        retrieved = test_db.get_val("complex")
        
        assert retrieved == complex_data
    
    def test_kv_store_default_value(self, test_db):
        """Проверка дефолтного значения для несуществующего ключа"""
        value = test_db.get_val("nonexistent", default="default_value")
        assert value == "default_value"
    
    def test_kv_store_update(self, test_db):
        """Проверка обновления значения"""
        test_db.set_val("key", "old_value")
        test_db.set_val("key", "new_value")
        
        value = test_db.get_val("key")
        assert value == "new_value"
    
    def test_telegram_outbox_add(self, test_db):
        """Проверка добавления сообщения в очередь Telegram"""
        result = test_db.add_tg_message("Test message", priority=1)
        assert result is True
    
    def test_telegram_outbox_get_pending(self, test_db):
        """Проверка получения сообщений из очереди"""
        test_db.add_tg_message("Message 1", priority=0)
        test_db.add_tg_message("Message 2", priority=1)
        
        messages = test_db.get_pending_tg_messages()
        assert len(messages) == 2
        
        # Проверяем структуру
        msg_id, msg_text, created_at = messages[0]
        assert isinstance(msg_id, int)
        assert msg_text == "Message 1"
        assert created_at is not None
    
    def test_telegram_mark_sent(self, test_db):
        """Проверка пометки сообщения как отправленного"""
        test_db.add_tg_message("Test message")
        messages = test_db.get_pending_tg_messages()
        
        msg_id = messages[0][0]
        test_db.mark_tg_sent(msg_id)
        
        # Проверяем что сообщение удалено
        messages_after = test_db.get_pending_tg_messages()
        assert len(messages_after) == 0
    
    def test_database_recovery_on_corruption(self, temp_dir):
        """Проверка восстановления при повреждении БД"""
        db_path = temp_dir / "corrupt.db"
        
        # Создаем поврежденный файл
        with open(db_path, "wb") as f:
            f.write(b"corrupted data")
        
        db = DBManager(str(db_path))
        
        # Должна создаться новая БД
        assert db.is_functional is True
        assert db.was_recovered is True
        
        # Старый файл должен быть изолирован
        corrupt_files = list(temp_dir.glob("corrupt.db.corrupt_*"))
        assert len(corrupt_files) == 1
