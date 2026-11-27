-- Поиск name ILIKE '%q%': B-tree бесполезен, нужен GIN-индекс по триграммам
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_name_trgm
    ON products USING gin (name gin_trgm_ops);

-- Топ продаж: INCLUDE кладёт нужные столбцы прямо в индекс
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_created_at
    ON orders (created_at) INCLUDE (product_id, quantity);

-- Внешний ключ: PostgreSQL НЕ создаёт на него индекс сам
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_product_id
    ON orders (product_id);

-- Частичный индекс: только необработанные заказы
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_orders_pending
    ON orders (id) WHERE status = 'pending';

-- Список товаров категории с сортировкой по цене (Сделайте сами)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_category_price
    ON products (category_id, price DESC);

ANALYZE products;
ANALYZE orders;
