-- Template: monthly_revenue_trend
-- Metrics: orders, gross_order_revenue, average_order_value
-- Base: orders
-- Time grain: month (fixed for this template)
-- Date field: orders.created_at

SELECT
    DATE_TRUNC('month', o.created_at)                                                  AS month,
    COUNT(DISTINCT o.order_id)                                                         AS orders,
    SUM(o.price_usd)                                                                   AS gross_order_revenue,
    SUM(o.price_usd) / NULLIF(COUNT(DISTINCT o.order_id), 0)                          AS average_order_value
FROM orders o
WHERE o.created_at >= '{start_date}'
  AND o.created_at <  '{end_date}'
GROUP BY
    DATE_TRUNC('month', o.created_at)
ORDER BY
    month
