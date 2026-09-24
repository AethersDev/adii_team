-- mart_daily_revenue: orders and revenue per day, from the staged orders.
SELECT order_date AS day, COUNT(*) AS orders, SUM(amount_usd) AS revenue_usd
FROM stg_orders
GROUP BY order_date;
