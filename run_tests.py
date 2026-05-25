#!/usr/bin/env python3
"""
Скрипт для запуска тестов с различными опциями.

Использование:
    python run_tests.py              # Запуск всех тестов
    python run_tests.py unit         # Запуск только unit тестов
    python run_tests.py integration  # Запуск только integration тестов
    python run_tests.py e2e          # Запуск только e2e тестов
    python run_tests.py coverage     # Запуск с отчетом о покрытии
    python run_tests.py html         # Запуск с HTML отчетом
    python run_tests.py ci           # Запуск для CI (все тесты + coverage + junit)
"""

import sys
import subprocess
import os


def run_command(cmd, description):
    """Выполняет команду и выводит результат."""
    print(f"\n{'='*60}")
    print(f"[TEST] {description}")
    print(f"{'='*60}")
    print(f"Команда: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=False)
    return result.returncode


def main():
    """Главная функция."""
    # Определяем аргумент
    test_type = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    base_cmd = ["python", "-m", "pytest"]
    
    # Базовые конфигурации для разных типов тестов
    configs = {
        "all": {
            "cmd": base_cmd + ["-v", "--tb=short", "--color=yes"],
            "desc": "Запуск всех тестов"
        },
        "unit": {
            "cmd": base_cmd + ["-v", "-m", "unit", "--tb=short"],
            "desc": "Запуск unit тестов"
        },
        "integration": {
            "cmd": base_cmd + ["-v", "-m", "integration", "--tb=short"],
            "desc": "Запуск интеграционных тестов"
        },
        "e2e": {
            "cmd": base_cmd + ["-v", "-m", "e2e", "--tb=short"],
            "desc": "Запуск end-to-end тестов"
        },
        "smoke": {
            "cmd": base_cmd + ["-v", "-m", "smoke", "--tb=short"],
            "desc": "Запуск smoke тестов"
        },
        "slow": {
            "cmd": base_cmd + ["-v", "-m", "slow", "--tb=short"],
            "desc": "Запуск медленных тестов"
        },
        "not-slow": {
            "cmd": base_cmd + ["-v", "-m", "not slow", "--tb=short"],
            "desc": "Запуск быстрых тестов (без slow)"
        },
        "coverage": {
            "cmd": base_cmd + [
                "-v", "--cov=promouters", "--cov-report=term-missing",
                "--cov-report=term:skip-covered"
            ],
            "desc": "Запуск всех тестов с отчетом о покрытии"
        },
        "html": {
            "cmd": base_cmd + [
                "-v", "--cov=promouters", "--cov-report=html",
                "--html=reports/report.html"
            ],
            "desc": "Запуск тестов с HTML отчетами"
        },
        "ci": {
            "cmd": base_cmd + [
                "-v", "--cov=promouters", "--cov-report=xml",
                "--cov-report=term", "--junitxml=reports/junit.xml",
                "--tb=short"
            ],
            "desc": "Запуск тестов для CI/CD"
        },
        "verbose": {
            "cmd": base_cmd + ["-vv", "--tb=long", "--color=yes", "-s"],
            "desc": "Подробный вывод всех тестов"
        },
        "parallel": {
            "cmd": base_cmd + ["-v", "-n", "auto", "--tb=short"],
            "desc": "Параллельный запуск тестов"
        },
    }
    
    if test_type not in configs:
        print(f"[ERROR] Неизвестный тип тестов: {test_type}")
        print("\nДоступные варианты:")
        for key in configs:
            print(f"  - {key}")
        print("\nПримеры:")
        print("  python run_tests.py              # Все тесты")
        print("  python run_tests.py unit         # Только unit")
        print("  python run_tests.py coverage     # С покрытием")
        print("  python run_tests.py html         # С HTML отчетом")
        sys.exit(1)
    
    config = configs[test_type]
    
    # Создаем директории для отчетов если нужно
    if test_type in ["html", "ci"]:
        os.makedirs("reports", exist_ok=True)
    
    # Запускаем тесты
    exit_code = run_command(config["cmd"], config["desc"])
    
    # Выводим информацию о результатах
    print(f"\n{'='*60}")
    if exit_code == 0:
        print("[OK] Все тесты прошли успешно!")
    else:
        print(f"[FAIL] Тесты завершились с ошибками (код: {exit_code})")
    print(f"{'='*60}\n")
    
    # Дополнительная информация для HTML отчета
    if test_type == "html" and exit_code == 0:
        print("[INFO] HTML отчеты созданы:")
        print("   - coverage: htmlcov/index.html")
        print("   - test report: reports/report.html")
        print("\nОткройте htmlcov/index.html в браузере для просмотра покрытия.")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
