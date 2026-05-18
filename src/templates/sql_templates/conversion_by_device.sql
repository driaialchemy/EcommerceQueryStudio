-- Template: conversion_by_device
-- Metrics: sessions, orders, conversion_rate
-- Denominator: COUNT(DISTINCT website_sessions.website_session_id)
-- Join: website_sessions LEFT JOIN orders ON website_session_id
-- Date field: website_sessions.created_at

SELECT
    ws.device_type,
    COUNT(DISTINCT ws.website_session_id)                                              AS sessions,
    COUNT(DISTINCT o.website_session_id)                                               AS orders,
    COUNT(DISTINCT o.website_session_id) * 1.0
        / NULLIF(COUNT(DISTINCT ws.website_session_id), 0)                            AS conversion_rate
FROM website_sessions ws
LEFT JOIN orders o
    ON ws.website_session_id = o.website_session_id
WHERE ws.created_at >= '{start_date}'
  AND ws.created_at <  '{end_date}'
GROUP BY
    ws.device_type
ORDER BY
    sessions DESC
