-- Template: revenue_by_campaign
-- Metrics: orders, gross_order_revenue, average_order_value
-- Revenue source: orders.price_usd
-- Join: website_sessions JOIN orders ON website_session_id (INNER — revenue templates exclude non-converting sessions)
-- Date field: website_sessions.created_at (session acquisition date attribution policy)

SELECT
    ws.utm_source,
    ws.utm_campaign,
    COUNT(DISTINCT o.order_id)                                                         AS orders,
    SUM(o.price_usd)                                                                   AS gross_order_revenue,
    SUM(o.price_usd) / NULLIF(COUNT(DISTINCT o.order_id), 0)                          AS average_order_value
FROM website_sessions ws
JOIN orders o
    ON ws.website_session_id = o.website_session_id
WHERE ws.created_at >= '{start_date}'
  AND ws.created_at <  '{end_date}'
GROUP BY
    ws.utm_source,
    ws.utm_campaign
ORDER BY
    gross_order_revenue DESC
