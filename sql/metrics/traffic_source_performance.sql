SELECT
	u.traffic_source,
	COUNT(DISTINCT u.id) AS acquired_users,
	COUNT(DISTINCT o.order_id) AS total_orders,
	ROUND(COUNT(DISTINCT o.user_id)::numeric / COUNT(DISTINCT u.id) * 100, 2) AS user_conversion_rate,
	ROUND(AVG(oi.sale_price)::numeric, 2) AS avg_ticket
FROM raw_data.users u
LEFT JOIN raw_data.orders o ON u.id = o.user_id
LEFT JOIN raw_data.order_items oi ON o.order_id = oi.order_id
GROUP BY 1
ORDER BY 5 DESC;

COMMENT ON VIEW analytics.traffic_source_performance IS 'Métricas de aquisição e conversão de marketing agrupadas por origem de tráfego.';
COMMENT ON COLUMN analytics.traffic_source_performance.user_conversion_rate IS 'Percentual de usuários cadastrados no canal que realizaram pelo menos uma compra.';
COMMENT ON COLUMN analytics.traffic_source_performance.avg_ticket IS 'Ticket médio por item comprado pelos usuários deste canal.';
