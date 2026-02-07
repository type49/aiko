"""
Тесты для ActivationService
"""
import pytest
import time
from unittest.mock import Mock, patch
from core.activation_service import ActivationService


@pytest.mark.unit
class TestActivationService:
    """Тесты сервиса активации"""
    
    @pytest.fixture
    def activation_service(self, mock_ctx):
        """Фикстура сервиса активации"""
        return ActivationService(mock_ctx)
    
    def test_initialization(self, activation_service, mock_ctx):
        """Проверка инициализации"""
        assert activation_service.ctx is mock_ctx
        assert activation_service.bot_name == "айко"
        assert activation_service.threshold == 80
    
    def test_check_trigger_by_name(self, activation_service):
        """Проверка активации по имени"""
        with patch('core.activation_service.CommandMatcher.check_trigger') as mock_check:
            mock_check.return_value = (True, "включи музыку")
            
            is_active, clean_text = activation_service.check("айко включи музыку")
            
            assert is_active is True
            assert clean_text == "включи музыку"
            mock_check.assert_called_once()
    
    def test_check_active_window(self, activation_service, mock_ctx):
        """Проверка работы в активном окне"""
        # Устанавливаем недавнее время активации
        mock_ctx.last_activation_time = time.time() - 2.0  # 2 секунды назад
        mock_ctx.active_window = 5.0
        
        with patch('core.activation_service.CommandMatcher.check_trigger') as mock_check:
            mock_check.return_value = (False, None)  # Триггер не найден
            
            is_active, clean_text = activation_service.check("включи свет")
            
            assert is_active is True
            assert clean_text == "включи свет"
    
    def test_check_outside_window(self, activation_service, mock_ctx):
        """Проверка за пределами активного окна"""
        # Устанавливаем старое время активации
        mock_ctx.last_activation_time = time.time() - 10.0  # 10 секунд назад
        mock_ctx.active_window = 5.0
        
        with patch('core.activation_service.CommandMatcher.check_trigger') as mock_check:
            mock_check.return_value = (False, None)
            
            is_active, clean_text = activation_service.check("включи свет")
            
            assert is_active is False
            assert clean_text is None
    
    def test_extend_post_command_window(self, activation_service, mock_ctx):
        """Проверка продления окна после команды"""
        mock_ctx.active_window = 5.0
        mock_ctx.post_command_window = 3.0
        current_time = time.time()
        
        activation_service.extend_post_command_window()
        
        # Должно установить время так, чтобы осталось post_command_window секунд
        expected_time = current_time - (5.0 - 3.0)
        assert abs(mock_ctx.last_activation_time - expected_time) < 0.1
    
    def test_refresh_activation(self, activation_service, mock_ctx):
        """Проверка сброса таймера активации"""
        old_time = time.time() - 10.0
        mock_ctx.last_activation_time = old_time
        
        activation_service.refresh_activation()
        
        # Время должно обновиться на текущее
        assert mock_ctx.last_activation_time > old_time
        assert abs(mock_ctx.last_activation_time - time.time()) < 0.1
    
    def test_handle_timeouts_closes_window(self, activation_service, mock_ctx):
        """Проверка закрытия окна по таймауту"""
        mock_ctx.state = "active"
        mock_ctx.last_activation_time = time.time() - 10.0
        mock_ctx.active_window = 5.0
        
        set_state_cb = Mock()
        activation_service.handle_timeouts(set_state_cb)
        
        set_state_cb.assert_called_once_with("idle")
    
    def test_handle_timeouts_keeps_window_open(self, activation_service, mock_ctx):
        """Проверка что окно не закрывается если таймер еще активен"""
        mock_ctx.state = "active"
        mock_ctx.last_activation_time = time.time() - 2.0
        mock_ctx.active_window = 5.0
        
        set_state_cb = Mock()
        activation_service.handle_timeouts(set_state_cb)
        
        set_state_cb.assert_not_called()
    
    def test_handle_timeouts_ignores_non_active_state(self, activation_service, mock_ctx):
        """Проверка что таймаут не обрабатывается в неактивном состоянии"""
        mock_ctx.state = "idle"
        mock_ctx.last_activation_time = time.time() - 10.0
        
        set_state_cb = Mock()
        activation_service.handle_timeouts(set_state_cb)
        
        set_state_cb.assert_not_called()
