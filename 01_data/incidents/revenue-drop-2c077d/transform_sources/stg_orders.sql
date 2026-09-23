-- stg_orders: the orders each nightly load committed, one row per order.
-- A batch is staged up to the line the loader acknowledged.
SELECT o.order_id, o.order_date, o.distributor, o.amount_usd
FROM raw_orders o
JOIN load_log l ON l.batch_id = o.batch_id
WHERE o.line_no <= l.rows_loaded;
