-- Удаление заявок 60016, 60017, 60018, 60019
-- Сначала удаляем связанные записи в таблице stats
DELETE FROM stats 
WHERE order_id IN (
    SELECT id FROM orders WHERE order_number IN (60016, 60017, 60018, 60019)
);

-- Затем удаляем сами заявки
DELETE FROM orders 
WHERE order_number IN (60016, 60017, 60018, 60019);

-- Проверяем результат
SELECT COUNT(*) as deleted_count 
FROM orders 
WHERE order_number IN (60016, 60017, 60018, 60019);

