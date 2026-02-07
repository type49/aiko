# Тестирование Aiko Assistant

## Установка зависимостей

```bash
pip install -r requirements-test.txt
```

## Запуск тестов

### Запуск всех тестов
```bash
pytest
```

### Запуск с покрытием кода
```bash
pytest --cov=. --cov-report=html --cov-report=term
```

### Запуск конкретного файла
```bash
pytest tests/test_config_manager.py
```

### Запуск конкретного теста
```bash
pytest tests/test_config_manager.py::TestConfigManager::test_create_default_config
```

### Запуск по маркерам
```bash
# Только unit-тесты
pytest -m unit

# Только интеграционные тесты
pytest -m integration

# Пропустить медленные тесты
pytest -m "not slow"

# Пропустить тесты требующие аудио
pytest -m "not audio"
```

## Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры
├── test_global_context.py   # Тесты глобального контекста
├── test_config_manager.py   # Тесты конфигурации
├── test_matcher.py          # Тесты нечеткого поиска
├── test_db_manager.py       # Тесты базы данных
├── test_plugin_loader.py    # Тесты загрузчика плагинов
├── test_activation_service.py  # Тесты активации
└── test_plugin_router.py    # Тесты роутера команд
```

## Маркеры

- `@pytest.mark.unit` - Быстрые unit-тесты
- `@pytest.mark.integration` - Интеграционные тесты
- `@pytest.mark.slow` - Медленные тесты
- `@pytest.mark.audio` - Требуют аудио оборудование
- `@pytest.mark.db` - Требуют базу данных

## Покрытие кода

После запуска с флагом `--cov-report=html` откройте `htmlcov/index.html` в браузере для детального анализа покрытия.

## Фикстуры

### Основные фикстуры (conftest.py)

- `temp_dir` - Временная директория для тестов
- `mock_config` - Мок конфигурации
- `mock_ctx` - Мок контекста AikoContext
- `test_db` - Тестовая база данных
- `mock_plugin` - Базовый мок плагина
- `clear_singleton_cache` - Очистка синглтонов между тестами

## TODO: Что еще нужно покрыть тестами

1. **STTService** - тесты распознавания речи
2. **AudioHandler** - тесты работы с аудио (сложно, требуют мока sounddevice)
3. **TaskScheduler** - тесты планировщика задач
4. **IntentClassifier** - тесты NLU классификатора
5. **AikoCore** - интеграционные тесты основного цикла
6. **AikoContext** - тесты методов контекста
7. **Плагины** - тесты конкретных плагинов из папки plugins/
8. **GUI компоненты** - тесты UI (если необходимо)
9. **Telegram бот** - тесты интеграции с Telegram

## Лучшие практики

1. **Изоляция** - каждый тест независим
2. **Моки** - используем моки для внешних зависимостей
3. **Фикстуры** - переиспользуем общий код через фикстуры
4. **Именование** - тесты имеют понятные имена описывающие проверку
5. **Один assert** - по возможности один концептуальный assert на тест
6. **Быстрота** - unit-тесты должны выполняться быстро

## Непрерывная интеграция (CI)

Пример конфигурации для GitHub Actions:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```
