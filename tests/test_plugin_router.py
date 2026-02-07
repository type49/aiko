"""
Тесты для CommandRouter
"""
import pytest
from unittest.mock import Mock, MagicMock
from core.plugin_router import CommandRouter


@pytest.mark.unit
class TestCommandRouter:
    """Тесты маршрутизатора команд"""
    
    @pytest.fixture
    def mock_nlu(self):
        """Мок NLU классификатора"""
        nlu = Mock()
        nlu.predict = Mock(return_value=None)
        return nlu
    
    @pytest.fixture
    def router(self, mock_nlu, mock_plugin):
        """Базовый роутер с одним плагином"""
        intent_map = {"тест": [mock_plugin]}
        fallbacks = []
        return CommandRouter(mock_nlu, intent_map, fallbacks)
    
    def test_initialization(self, router, mock_nlu):
        """Проверка инициализации роутера"""
        assert router.nlu is mock_nlu
        assert len(router.intent_map) == 1
        assert len(router.fallbacks) == 0
    
    def test_route_nlu_success(self, mock_nlu, mock_ctx):
        """Проверка маршрутизации через NLU"""
        plugin = Mock()
        plugin.execute = Mock(return_value=True)
        plugin.__class__.__name__ = "TestPlugin"
        
        mock_nlu.predict = Mock(return_value=plugin)
        
        router = CommandRouter(mock_nlu, {}, [])
        result = router.route("какая-то фраза", mock_ctx)
        
        assert result is True
        plugin.execute.assert_called_once_with("какая-то фраза", mock_ctx)

    def test_route_trigger_match(self, router, mock_plugin, mock_ctx):
        """Проверка маршрутизации через триггеры"""
        # Убираем неработающий 'with Mock()'
        result = router.route("тест команда", mock_ctx)

        # Теперь проверяем результат
        assert result is True
        assert mock_plugin.execute.called
    
    def test_route_fallback(self, mock_nlu, mock_ctx):
        """Проверка маршрутизации через fallback"""
        fallback = Mock()
        fallback.execute = Mock(return_value=True)
        fallback.__class__.__name__ = "FallbackPlugin"
        
        router = CommandRouter(mock_nlu, {}, [fallback])
        result = router.route("неизвестная команда", mock_ctx)
        
        assert result is True
        fallback.execute.assert_called_once()
    
    def test_route_no_match(self, mock_nlu, mock_ctx):
        """Проверка когда ни один плагин не подошел"""
        router = CommandRouter(mock_nlu, {}, [])
        result = router.route("неизвестная команда", mock_ctx)
        
        assert result is False
    
    def test_route_plugin_returns_false(self, router, mock_plugin, mock_ctx):
        """Проверка когда плагин отклоняет выполнение"""
        mock_plugin.execute = Mock(return_value=False)
        
        result = router.route("тест", mock_ctx)
        
        assert result is False
    
    def test_route_tries_next_candidate_on_failure(self, mock_nlu, mock_ctx):
        """Проверка попытки следующего кандидата при отказе"""
        # Первый плагин отказывается
        plugin1 = Mock()
        plugin1.execute = Mock(return_value=False)
        plugin1.__class__.__name__ = "Plugin1"
        
        # Второй плагин принимает
        plugin2 = Mock()
        plugin2.execute = Mock(return_value=True)
        plugin2.__class__.__name__ = "Plugin2"
        
        fallbacks = [plugin2]
        mock_nlu.predict = Mock(return_value=plugin1)
        
        router = CommandRouter(mock_nlu, {}, fallbacks)
        result = router.route("команда", mock_ctx)
        
        assert result is True
        plugin1.execute.assert_called_once()
        plugin2.execute.assert_called_once()
    
    def test_route_exception_handling(self, router, mock_plugin, mock_ctx, caplog):
        """Проверка обработки исключений в плагинах"""
        mock_plugin.execute = Mock(side_effect=Exception("Test error"))
        
        result = router.route("тест", mock_ctx)
        
        assert result is False
        assert "ERR" in caplog.text
        assert "Test error" in caplog.text
    
    def test_route_avoids_duplicate_tries(self, mock_nlu, mock_ctx):
        """Проверка что плагин не пробуется дважды"""
        plugin = Mock()
        plugin.execute = Mock(return_value=False)
        plugin.__class__.__name__ = "DupePlugin"
        
        # Плагин появляется и в NLU, и в fallbacks
        mock_nlu.predict = Mock(return_value=plugin)
        fallbacks = [plugin]
        
        router = CommandRouter(mock_nlu, {}, fallbacks)
        router.route("команда", mock_ctx)
        
        # Должен быть вызван только один раз
        assert plugin.execute.call_count == 1
    
    def test_get_candidates_order(self, mock_nlu):
        """Проверка порядка кандидатов: NLU -> Triggers -> Fallbacks"""
        nlu_plugin = Mock()
        nlu_plugin.__class__.__name__ = "NLUPlugin"
        
        trigger_plugin = Mock()
        trigger_plugin.__class__.__name__ = "TriggerPlugin"
        
        fallback_plugin = Mock()
        fallback_plugin.__class__.__name__ = "FallbackPlugin"
        
        mock_nlu.predict = Mock(return_value=nlu_plugin)
        
        router = CommandRouter(
            mock_nlu,
            {"ключ": [trigger_plugin]},
            [fallback_plugin]
        )
        
        candidates = list(router._get_candidates("тест ключ"))
        
        # NLU должен быть первым
        assert candidates[0][0] is nlu_plugin
        assert candidates[0][1] == "NLU"
