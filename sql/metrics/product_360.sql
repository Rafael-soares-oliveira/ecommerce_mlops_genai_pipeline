WITH sales_metrics AS (
	SELECT
		oi.product_id,

		-- Taxa de Devolução (Itens devolvidos / Total Itens Entregues ou Completos -> desconsiderado 'Processing' e 'Cancelled')
		(
			COUNT(CASE WHEN oi.status = 'Returned' THEN 1 END)::numeric /
			NULLIF(COUNT(CASE WHEN oi.status IN ('Complete', 'Returned', 'Shipped') THEN 1 END), 0)
		) AS return_rate,

		-- Tempo de Envio: extrai os segundos e converte para dias (86400s = 24h)
		AVG(EXTRACT(epoch FROM (oi.shipped_at - oi.created_at))/86400) AS avg_to_shipping_days,

		-- Average Ticket (AOV)
		AVG(oi.sale_price) AS aov
	FROM raw_data.order_items oi
	JOIN raw_data.products p ON oi.product_id = p.id
	WHERE oi.status NOT IN ('Cancelled')
	GROUP BY 1
),
stock_metrics AS (
	SELECT
		ii.product_id,

		-- Aging do Estoque (Média de dias dos itens parados(não vendidos))
		AVG(current_date - ii.created_at::date) AS avg_aging_days,
		COUNT(*) AS stock_qt
	FROM raw_data.inventory_items ii
	WHERE ii.sold_at IS null -- Não vendido
	GROUP BY 1
)
SELECT
	p.category,
	p.name AS product_name,
	ROUND(sa.return_rate * 100, 2) AS return_rate_pct,
	ROUND(sa.avg_to_shipping_days::numeric, 2) AS avg_to_shipping_days,
	ROUND(
		((sa.aov - p.cost) / nullif(sa.aov, 0)) * 100, 2
	) AS avg_margin_pct,
	ROUND(sa.aov, 2) AS aov,
	ROUND(st.avg_aging_days, 2) AS avg_aging_days,
	COALESCE(stock_qt, 0) AS stock_qt
FROM raw_data.products p
LEFT JOIN sales_metrics sa ON p.id = sa.product_id
LEFT JOIN stock_metrics st ON p.id = st.product_id
ORDER BY avg_aging_days DESC;

COMMENT ON VIEW analytics.product_performance IS 'Visão consolidada de performance de produtos. Une métricas de vendas (margem, devolução, ticket médio) com saúde de estoque (aging e quantidade).';
COMMENT ON COLUMN analytics.product_performance.avg_aging_days IS 'Média de dias que o estoque do produto está parado (sem vender).';
COMMENT ON COLUMN analytics.product_performance.avg_margin_pct IS 'Margem de lucro média em percentual (AOV - Custo / AOV).';
COMMENT ON COLUMN analytics.product_performance.return_rate_pct IS 'Taxa percentual de devolução do produto.';
