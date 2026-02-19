WITH funil AS (
	SELECT
		EXTRACT(YEAR FROM created_at) AS year,
		session_id,
		MAX(CASE WHEN event_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
		MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) AS has_purchase,
		MAX(CASE WHEN extracted_product_id IS NOT NULL THEN 1 ELSE 0 END) AS has_product_view
	FROM raw_data.events
	GROUP BY 1, 2
)
SELECT
	YEAR,
	COUNT(*) AS total_sessions,
	ROUND(AVG(has_cart) * 100, 2) AS added_cart,
	ROUND(AVG(has_purchase) * 100, 2) AS purchased,
	ROUND(
		COUNT(*) FILTER (WHERE has_cart = 1 AND has_purchase = 0)::numeric /
		NULLIF(COUNT(*) FILTER (WHERE has_cart = 1), 0) * 100,
		2
	) AS abandon_cart,
	ROUND(
		COUNT(*) FILTER (WHERE has_product_view = 1 AND has_cart = 0)::numeric /
		NULLIF(COUNT(*) FILTER (WHERE has_product_view = 1), 0) * 100,
		2
	) AS drop_off
FROM funil
GROUP BY 1
ORDER BY 1;

COMMENT ON VIEW analytics.sales_funnel IS 'Métricas de funil de conversão agregadas por ano. Acompanha a jornada do usuário desde a visualização até a compra e taxas de abandono.';
COMMENT ON COLUMN analytics.sales_funnel.abandon_cart IS 'Taxa de abandono de carrinho (%). Usuários que adicionaram ao carrinho mas não compraram.';
COMMENT ON COLUMN analytics.sales_funnel.drop_off IS 'Taxa de desistência (%). Usuários que viram um produto mas não adicionaram ao carrinho.';
