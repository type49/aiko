import pytest
from utils.matcher import CommandMatcher

# Параметризация позволяет прогнать один тест на разных данных
@pytest.mark.parametrize("input_text, trigger, expected_bool", [
    ("диагностика системы", "диагностика системы", True), # Идеал
    ("диагностика систем", "диагностика системы", True),  # Опечатка
    ("включи свет", "диагностика системы", False),        # Чушь
    ("", "диагностика системы", False),                   # Пустота
])
def test_fuzzy_matching_strict(input_text, trigger, expected_bool):
    """Проверяем, что мэтчер корректно распознает команды"""
    match, score = CommandMatcher.extract(input_text, [trigger], threshold=70)
    assert (match is not None) == expected_bool