"""
Тесты для глобального реестра контекста
"""
import pytest
from core.global_context import (
    set_global_context,
    get_context,
    ctx,
    require_context
)


@pytest.mark.unit
class TestGlobalContext:
    """Тесты глобального контекста"""
    
    def test_set_and_get_context(self, mock_ctx):
        """Проверка установки и получения контекста"""
        set_global_context(mock_ctx)
        assert get_context() is mock_ctx
        assert ctx() is mock_ctx
    
    def test_get_context_when_not_set(self):
        """Проверка получения контекста когда он не установлен"""
        # Контекст сброшен через фикстуру clear_singleton_cache
        assert get_context() is None
        assert ctx() is None
    
    def test_require_context_raises_when_not_set(self):
        """Проверка что require_context бросает исключение"""
        with pytest.raises(RuntimeError, match="Context not initialized"):
            require_context()
    
    def test_require_context_returns_when_set(self, mock_ctx):
        """Проверка что require_context возвращает контекст"""
        set_global_context(mock_ctx)
        assert require_context() is mock_ctx
    
    def test_context_can_be_overwritten(self, mock_ctx):
        """Проверка что контекст можно перезаписать"""
        set_global_context(mock_ctx)
        
        new_ctx = object()
        set_global_context(new_ctx)
        
        assert get_context() is new_ctx
        assert get_context() is not mock_ctx
