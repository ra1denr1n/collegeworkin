\echo '=== План: список товаров категории ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, price, stock FROM products
WHERE category_id = 7 ORDER BY price DESC LIMIT 20;

\echo '=== План: поиск по подстроке ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT id, name, price FROM products WHERE name ILIKE '%a3f%' LIMIT 20;

\echo '=== План: топ продаж ==='
EXPLAIN (ANALYZE, BUFFERS)
SELECT product_id, sum(quantity) AS sold FROM orders
WHERE created_at > now() - interval '7 days'
GROUP BY product_id ORDER BY sold DESC LIMIT 10;

\echo '=== Топ-10 запросов по суммарному времени ==='
SELECT calls,
       round(total_exec_time::numeric, 1) AS total_ms,
       round(mean_exec_time::numeric, 2)  AS avg_ms,
       left(regexp_replace(query, '\s+', ' ', 'g'), 80) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
