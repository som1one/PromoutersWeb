# Руководство по тестированию СУУПР

## Структура тестов

```
tests/
├── __init__.py              # Инициализация пакета тестов
├── conftest.py              # Общие фикстуры для всех тестов
├── test_models.py           # Юнит-тесты моделей
├── test_services.py         # Интеграционные тесты сервисов
├── test_data_factories.py   # Тесты с фабриками данных
└── test_fixtures_demo.py    # Демонстрация использования фикстур
```

## Маркеры тестов

| Маркер | Описание | Как запустить |
|--------|----------|---------------|
| `unit` | Быстрые тесты отдельных компонентов | `pytest -m unit` |
| `integration` | Тесты взаимодействия компонентов | `pytest -m integration` |
| `e2e` | End-to-end тесты полных сценариев | `pytest -m e2e` |
| `smoke` | Быстрая проверка основного функционала | `pytest -m smoke` |
| `slow` | Медленные тесты | `pytest -m slow` |

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Запуск всех тестов

```bash
# Базовый запуск
pytest

# Через скрипт
python run_tests.py

# Подробный вывод
python run_tests.py verbose
```

### 3. Запуск по категориям

```bash
# Только unit тесты
python run_tests.py unit

# Только интеграционные
python run_tests.py integration

# Smoke тесты (быстрая проверка)
python run_tests.py smoke
```

## Покрытие кода (Coverage)

### HTML отчет

```bash
python run_tests.py html
```

После выполнения откройте `htmlcov/index.html` в браузере.

### Консольный отчет

```bash
python run_tests.py coverage
```

Выводит таблицу покрытия прямо в консоль.

## Доступные фикстуры

### Модели

| Фикстура | Описание |
|----------|----------|
| `active_promotion` | Активная промо-акция |
| `inactive_promotion` | Неактивная (черновик) |
| `expired_promotion` | Истекшая по дате |
| `limited_promotion` | С ограничением использований (3) |
| `unlimited_promotion` | Без ограничений |
| `regular_user` | Обычный пользователь (баланс 5000) |
| `premium_user` | Премиум (баланс 50000) |
| `new_user` | Новый (баланс 0) |
| `inactive_user` | Неактивный |
| `empty_order` | Пустой заказ |
| `sample_order` | Заказ с товарами |
| `large_order` | Крупный заказ |
| `small_order` | Мелкий заказ |

### Сервисы

| Фикстура | Описание |
|----------|----------|
| `promotion_service` | Чистый PromotionService |
| `user_service` | Чистый UserService |
| `order_service` | OrderService с зависимостями |
| `multiple_promotions` | 4 акции разных типов |
| `multiple_users` | 3 пользователя |

### Данные

| Фикстура | Описание |
|----------|----------|
| `sample_promotion_data` | Словарь с данными акции |
| `sample_user_data` | Словарь с данными пользователя |
| `param_promotion` | Параметризованная (3 варианта) |

## Примеры использования фикстур

```python
# Простой тест с фикстурами
def test_apply_promotion(active_promotion, sample_order):
    discount = sample_order.apply_promotion(active_promotion)
    assert discount > 0

# Несколько фикстур
def test_full_flow(
    promotion_service,
    user_service,
    order_service,
    multiple_promotions,
):
    # Ваш тест здесь
    pass
```

## Структура тестового файла

```python
import pytest
from decimal import Decimal

# Маркер для категории тестов
@pytest.mark.unit
class TestMyFeature:
    """Группировка тестов в класс."""
    
    def test_something(self, active_promotion):
        """Тест с описанием."""
        assert active_promotion.is_active()
    
    @pytest.mark.parametrize("discount", [10, 20, 30])
    def test_with_params(self, discount):
        """Параметризованный тест."""
        assert 0 < discount <= 100
```

## Полезные команды Pytest

```bash
# Показать все тесты без запуска
pytest --collect-only

# Запустить конкретный тест
pytest tests/test_models.py::TestPromotion::test_promotion_creation -v

# Запустить тесты по имени (содержит "discount")
pytest -k "discount" -v

# Остановиться на первом падении
pytest -x

# Показать локальные переменные при падении
pytest -l

# Запустить последний упавший
pytest --lf

# Запустить в случайном порядке
pytest --random-order

# Профилирование (самые медленные)
pytest --durations=10
```

## CI/CD интеграция

```bash
# Для Jenkins/GitLab CI
python run_tests.py ci
```

Создает:
- `coverage.xml` — для плагинов покрытия
- `reports/junit.xml` — для отображения тестов в CI

## Проверка кода

```bash
# Форматирование
black promouters/ tests/

# Сортировка импортов
isort promouters/ tests/

# Линтер
flake8 promouters/ tests/

# Типы
mypy promouters/
```

## Частые проблемы

### Тесты не находят фикстуры
- Проверьте что `conftest.py` в папке `tests/`
- Фикстуры из `conftest.py` автоматически доступны во всех тестах

### Ошибки импорта
- Установите пакет в editable режим: `pip install -e .`
- Или добавьте корень проекта в PYTHONPATH

### Медленные тесты
```bash
# Исключить slow
pytest -m "not slow"

# Параллельный запуск
pytest -n auto
```
