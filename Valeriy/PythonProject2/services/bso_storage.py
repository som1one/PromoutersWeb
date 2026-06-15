"""
Единый сервис для сохранения и поиска БСО файлов.
Гарантирует консистентность между ботом и веб-интерфейсом.
"""
import os
import time
import logging
from pathlib import Path
from typing import Optional
import requests

logger = logging.getLogger(__name__)

# Единая директория для БСО (volume, общая для всех контейнеров)
BSO_STORAGE_DIR = Path("/app/data/bso_files")

# Резервные директории (на случай проблем с volume)
FALLBACK_DIRS = [
    Path("data/bso_files"),  # Относительный путь
    Path("bso_files"),  # Старая директория
]


def ensure_storage_dir() -> Path:
    """
    Создаёт директорию для хранения БСО и возвращает путь к ней.
    Пробует несколько вариантов, начиная с volume.
    """
    for storage_dir in [BSO_STORAGE_DIR] + FALLBACK_DIRS:
        try:
            storage_dir.mkdir(parents=True, exist_ok=True)
            # Проверяем, что можем писать
            test_file = storage_dir / ".test_write"
            try:
                test_file.write_text("test")
                test_file.unlink()
                logger.info(f"✅ Директория БСО готова: {storage_dir}")
                return storage_dir
            except Exception as e:
                logger.warning(f"Не удалось записать в {storage_dir}: {e}")
                continue
        except Exception as e:
            logger.warning(f"Не удалось создать директорию {storage_dir}: {e}")
            continue
    
    # Если ничего не сработало, используем текущую директорию
    fallback = Path(".").resolve() / "bso_files"
    fallback.mkdir(exist_ok=True)
    logger.warning(f"⚠️ Используется резервная директория: {fallback}")
    return fallback


def generate_bso_filename(order_id: int, extension: str = ".jpg") -> str:
    """Генерирует уникальное имя файла БСО"""
    timestamp = int(time.time())
    return f"bso_{order_id}_{timestamp}{extension}"


def save_bso_from_url(order_id: int, url: str, filename: Optional[str] = None) -> Optional[str]:
    """
    Скачивает БСО по URL и сохраняет в хранилище.
    
    Args:
        order_id: ID заявки
        url: URL файла для скачивания
        filename: Имя файла (если не указано, генерируется автоматически)
    
    Returns:
        Относительный путь к файлу для сохранения в БД (например, "bso_123_1234567890.jpg")
        или None в случае ошибки
    """
    try:
        # Определяем расширение файла
        if not filename:
            # Пытаемся определить расширение из URL
            ext = ".jpg"  # По умолчанию
            if ".pdf" in url.lower():
                ext = ".pdf"
            elif ".png" in url.lower():
                ext = ".png"
            elif ".webp" in url.lower():
                ext = ".webp"
            filename = generate_bso_filename(order_id, ext)
        else:
            # Если имя передано, добавляем префикс заявки
            if not filename.startswith(f"bso_{order_id}_"):
                _, ext = os.path.splitext(filename)
                filename = generate_bso_filename(order_id, ext)
        
        # Получаем директорию для сохранения
        storage_dir = ensure_storage_dir()
        file_path = storage_dir / filename
        
        # Скачиваем файл
        logger.info(f"Скачивание БСО для заявки {order_id} из {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.content
        
        if not content or len(content) == 0:
            logger.warning(f"Пустой контент БСО для заявки {order_id}")
            return None
        
        # Сохраняем файл
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Проверяем, что файл записался
        if not file_path.exists() or file_path.stat().st_size == 0:
            logger.error(f"❌ Файл БСО не записался: {file_path}")
            return None
        
        logger.info(f"✅ БСО сохранён для заявки {order_id}: {file_path} ({file_path.stat().st_size} байт)")
        
        # Возвращаем только имя файла для сохранения в БД
        # Это гарантирует, что поиск будет работать независимо от абсолютного пути
        return filename
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении БСО из URL для заявки {order_id}: {e}")
        return None


def save_bso_from_bytes(order_id: int, content: bytes, filename: Optional[str] = None) -> Optional[str]:
    """
    Сохраняет БСО из байтов в хранилище.
    
    Args:
        order_id: ID заявки
        content: Содержимое файла в байтах
        filename: Имя файла (если не указано, генерируется автоматически)
    
    Returns:
        Имя файла для сохранения в БД или None в случае ошибки
    """
    try:
        if not filename:
            filename = generate_bso_filename(order_id, ".jpg")
        else:
            # Если имя передано, но не соответствует формату bso_{order_id}_{timestamp}.ext,
            # генерируем новое с сохранением расширения
            _, ext = os.path.splitext(filename)
            if not ext:
                ext = ".jpg"  # По умолчанию, если расширения нет
            if not filename.startswith(f"bso_{order_id}_"):
                filename = generate_bso_filename(order_id, ext)
        
        storage_dir = ensure_storage_dir()
        file_path = storage_dir / filename
        
        # Сохраняем файл
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Проверяем сохранение
        if not file_path.exists() or file_path.stat().st_size != len(content):
            logger.error(f"❌ Файл БСО не записался корректно: {file_path}")
            return None
        
        logger.info(f"✅ БСО сохранён для заявки {order_id}: {file_path} ({len(content)} байт)")
        return filename
        
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении БСО из байтов для заявки {order_id}: {e}")
        return None


def find_bso_file(order_id: int, filename: Optional[str] = None) -> Optional[Path]:
    """
    Находит файл БСО для заявки.
    
    Args:
        order_id: ID заявки
        filename: Имя файла из БД (может быть полным путём типа "data/bso_files/bso_123.jpg" 
                  или просто именем "bso_123.jpg")
    
    Returns:
        Абсолютный путь к файлу или None, если не найден
    """
    # Список директорий для поиска (в порядке приоритета)
    search_dirs = [BSO_STORAGE_DIR] + FALLBACK_DIRS + [Path(".").resolve()]
    
    # Если указано имя файла, ищем по нему
    if filename:
        # Очищаем путь от директорий, оставляем только имя файла
        # Поддерживаем старые форматы: "data/bso_files/bso_123.jpg", "bso_files/bso_123.jpg", "bso_123.jpg"
        filename_clean = Path(filename).name
        
        logger.info(f"Поиск БСО для заявки {order_id} по имени файла: {filename} -> {filename_clean}")
        
        for search_dir in search_dirs:
            candidate = search_dir / filename_clean
            if candidate.exists() and candidate.is_file():
                logger.info(f"✅ БСО найден для заявки {order_id}: {candidate}")
                return candidate
    
    # Если имя не указано или не найдено, ищем по паттерну
    logger.info(f"Поиск БСО для заявки {order_id} по паттерну bso_{order_id}_*")
    for search_dir in search_dirs:
        try:
            possible_files = list(search_dir.glob(f"bso_{order_id}_*"))
            if possible_files:
                # Берём самый новый файл
                found_file = max(possible_files, key=lambda p: p.stat().st_mtime)
                logger.info(f"✅ БСО найден по паттерну для заявки {order_id}: {found_file}")
                return found_file
        except Exception as e:
            logger.warning(f"Ошибка при поиске в {search_dir}: {e}")
            continue
    
    logger.warning(f"❌ БСО не найден для заявки {order_id}")
    return None


def get_bso_file_path(order_id: int, filename: Optional[str] = None) -> Optional[Path]:
    """
    Получает путь к файлу БСО. Алиас для find_bso_file для обратной совместимости.
    """
    return find_bso_file(order_id, filename)
