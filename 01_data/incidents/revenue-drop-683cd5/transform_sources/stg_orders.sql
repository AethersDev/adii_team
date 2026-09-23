-- stg_orders: the orders each nightly load committed, one row per order.
-- A batch is staged up to the line the loader acknowledged.
-- DATA-97: from 2026-03-11, leave the vendor's sandbox test orders out of staging.
SELECT o.order_id, o.order_date, o.distributor, o.amount_usd
FROM raw_orders o
JOIN load_log l ON l.batch_id = o.batch_id
WHERE o.line_no <= l.rows_loaded
  AND NOT (o.order_date >= '2026-03-11' AND o.distributor IN ('Northwind', 'Harbor'));
