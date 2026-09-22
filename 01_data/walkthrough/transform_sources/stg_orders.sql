-- stg_orders: one row per order, with the amount in dollars.
-- orders.amount_cents holds cents; convert to dollars for the mart.
SELECT order_id, order_date, amount_cents / 100.0 / 100.0 AS amount_usd
FROM orders;
