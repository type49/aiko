"""
Глобальный реестр контекста.
Позволяет безопасно получить ctx из любого места без прокидывания зависимостей.
"""

_context_instance = None


def set_global_context(ctx):
    """
    Регистрирует глобальный контекст (вызывается один раз при старте).
    """
    global _context_instance
    _context_instance = ctx


def get_context():
    """
    Получить текущий контекст из любого места.
    Возвращает None, если контекст еще не инициализирован.
    """
    return _context_instance


def ctx():
    """
    Короткий алиас для получения контекста.

    Использование:
        from global_context import ctx
        ctx().broadcast("Hello!")
    """
    return _context_instance


# Альтернативный вариант с исключением при отсутствии контекста
def require_context():
    """
    Получить контекст с гарантией, что он существует.
    Бросает исключение, если контекст не инициализирован.
    """
    if _context_instance is None:
        raise RuntimeError(
            "Context not initialized. Call set_global_context() first."
        )
    return _context_instance