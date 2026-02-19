WITH metrics AS (
	SELECT
		session_id,
		EXTRACT(epoch FROM (MAX(created_at) - MIN(created_at))) / 60 AS duration_min,
		MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase
	FROM raw_data.events
	GROUP BY 1
)
SELECT
	CASE
		WHEN duration_min < 1 THEN '0-1 min'
		WHEN duration_min < 5 THEN '1-5 min'
		WHEN duration_min < 10 THEN '5-10 min'
		ELSE '10+ min'
	END AS session_duration_bucket,
	COUNT(*) AS total_sessions,
	SUM(has_purchase) AS total_sales,
	ROUND(AVG(has_purchase) * 100, 2) AS conversion_rate
FROM metrics
GROUP BY 1
ORDER BY MIN(duration_min);

COMMENT ON VIEW analytics.session_conversion IS 'Métricas de conversão de vendas agrupadas por tempo de duração da sessão do usuário.';
COMMENT ON COLUMN analytics.session_conversion.session_duration_bucket IS 'Faixa de tempo da sessão (0-1 min, 1-5 min, 5-10 min, 10+ min).';
COMMENT ON COLUMN analytics.session_conversion.conversion_rate IS 'Taxa de conversão em % de sessões que resultaram em compra.';
