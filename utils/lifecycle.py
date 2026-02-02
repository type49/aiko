import os
import atexit
from utils.logger import logger

class AppLifecycle:
    def __init__(self, lock_file="session.lock"):
        self.lock_file = lock_file

    def check_previous_session(self):
        """Функциональный тест восстановления (Recovery Testing)"""
        if os.path.exists(self.lock_file):
            logger.error("!!! [BLACK BOX] Обнаружено аварийное завершение предыдущей сессии!")
            # Здесь в будущем будет вызов функции отправки в Telegram
            return False
        logger.info("Предыдущая сессия была завершена корректно.")
        return True

    def create_lock(self):
        """Создает метку активного процесса"""
        try:
            with open(self.lock_file, "w") as f:
                f.write(str(os.getpid())) # Записываем PID процесса
            logger.debug("Файл сессии (lock) создан.")
        except Exception as e:
            logger.error(f"Не удалось создать lock-файл: {e}")

    def cleanup(self):
        """Удаляет метку при чистом выходе"""
        if os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                logger.info("Файл сессии удален. Чистый выход зафиксирован.")
            except Exception as e:
                logger.error(f"Ошибка при удалении lock-файла: {e}")

# Создаем синглтон для удобного импорта
lifecycle = AppLifecycle()