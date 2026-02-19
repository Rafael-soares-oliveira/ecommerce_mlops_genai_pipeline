WITH metrics AS (
	SELECT
		CAST(DATE_TRUNC('day', oi.created_at) AS date) as day,
		u.country,
		COALESCE(SUM(oi.sale_price) FILTER (WHERE oi.status != 'Cancelled'), 0) AS gmv,
		COALESCE(SUM(oi.sale_price) FILTER (WHERE oi.status NOT IN ('Cancelled', 'Returned')), 0) AS net_revenue,
		COALESCE(SUM(p.cost) FILTER (WHERE oi.status NOT IN ('Cancelled', 'Returned')), 0) AS cogs_net,
		COALESCE(SUM(p.cost) FILTER (WHERE oi.status = 'Returned'), 0) AS cost_of_returns,
		CAST(COUNT(DISTINCT oi.order_id) FILTER (WHERE oi.status NOT IN ('Cancelled', 'Returned')) AS float) AS count_orders_valid,
		CAST(COUNT(DISTINCT oi.order_id) FILTER (WHERE oi.status = 'Cancelled') AS float) AS count_orders_cancelled,
		CAST(COUNT(DISTINCT oi.order_id) FILTER (WHERE oi.status = 'Returned') AS float) AS count_orders_returned,
		CAST(COUNT(DISTINCT oi.order_id) AS float) AS count_orders_total
	FROM raw_data.order_items oi
	JOIN raw_data.products p ON oi.product_id = p.id
	JOIN raw_data.users u ON oi.user_id = u.id
	GROUP BY 1, 2
	ORDER BY 1 DESC, 2
),
final_metrics AS (
	SELECT
		day,
		country,
		gmv,
		net_revenue,
		net_revenue - cogs_net AS gross_profit_optimistic,
		net_revenue - cogs_net - (cost_of_returns * 0.10) AS gross_profit_realistic,
		cost_of_returns * 0.10 AS logistic_loss,
		CASE
			WHEN count_orders_valid = 0
			THEN 0
			ELSE count_orders_cancelled / count_orders_total * 100
		END AS cancellation_rate,
		CASE
			WHEN count_orders_valid = 0
			THEN 0
			ELSE count_orders_returned/ count_orders_total * 100
		END AS returns_rate
	FROM metrics
)
SELECT
	day,
	country
	gmv,
	net_revenue,
	gross_profit_optimistic,
	gross_profit_realistic,
	logistic_loss,
	cancellation_rate::numeric(5, 2),
	returns_rate::numeric(5, 2)
FROM final_metrics;


COMMENT ON VIEW analytics.daily_sales IS 'Métricas financeiras e logísticas agregadas por dia e país. Use para analisar GMV, receita, lucro bruto e taxas de conversão/perda.';
COMMENT ON COLUMN analytics.daily_sales.gmv IS 'Volume Bruto de Mercadorias (vendas brutas). Exclui apenas pedidos cancelados.';
COMMENT ON COLUMN analytics.daily_sales.net_revenue IS 'Receita Líquida real. Exclui pedidos cancelados e devolvidos.';
COMMENT ON COLUMN analytics.daily_sales.gross_profit_realistic IS 'Lucro bruto considerando descontos de perdas logísticas (10% sobre o custo de devoluções).';
