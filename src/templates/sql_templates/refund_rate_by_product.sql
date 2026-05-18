-- Template: refund_rate_by_product
-- Metrics: items_sold, refund_amount, refund_rate
-- Base: order_items
-- Joins: order_items LEFT JOIN order_item_refunds ON order_item_id
--        order_items JOIN products ON product_id
-- Date field: order_items.created_at (item sale date attribution policy)
-- Refund attribution: item sale date, not refund event date

SELECT
    oi.product_id,
    p.product_name,
    COUNT(oi.order_item_id)                                                            AS items_sold,
    COUNT(oir.order_item_id)                                                           AS refunded_items,
    COUNT(oir.order_item_id) * 1.0
        / NULLIF(COUNT(oi.order_item_id), 0)                                          AS refund_rate,
    COALESCE(SUM(oir.refund_amount_usd), 0)                                            AS refund_amount
FROM order_items oi
LEFT JOIN order_item_refunds oir
    ON oi.order_item_id = oir.order_item_id
JOIN products p
    ON oi.product_id = p.product_id
WHERE oi.created_at >= '{start_date}'
  AND oi.created_at <  '{end_date}'
GROUP BY
    oi.product_id,
    p.product_name
ORDER BY
    refund_rate DESC
