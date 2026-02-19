WITH ref_date AS (
	SELECT max(created_at)::date + 1 AS snapshot_date
	FROM raw_data.order_items
	WHERE status NOT IN ('Cancelled', 'Returned')
),
customer_stats AS (
	SELECT
		u.id AS user_id,
		(SELECT snapshot_date FROM ref_date) - MAX(oi.created_at)::date AS recency_days,
		COUNT(DISTINCT oi.order_id) AS frequency_count,
		SUM(oi.sale_price) AS ltv,
		MIN(oi.created_at)::date AS first_purchase_date
	FROM raw_data.users u
	JOIN raw_data.order_items oi ON u.id = oi.user_id
	WHERE oi.status NOT IN ('Cancelled', 'Returned')
	GROUP BY 1
	),
rfm_scores AS (
	SELECT
		*,
		NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
		NTILE(5) OVER (ORDER BY frequency_count ASC) AS f_score,
		NTILE(5) OVER (ORDER BY ltv ASC) AS m_score
	FROM customer_stats
)
SELECT
	user_id,
	recency_days,
	frequency_count,
	ROUND(ltv::numeric, 2) AS ltv_value,
	CONCAT(r_score, f_score, m_score) AS rfm_score,
	r_score,
	f_score,
	m_score,
	CASE
		WHEN r_score >= 5 AND f_score >= 5 THEN 'Champions (VIP)'
		WHEN r_score >= 4 AND f_score >= 4 THEN 'Loyal Customers'
		WHEN r_score >= 3 AND f_score >= 3 THEN 'Potential Loyalist'
		WHEN r_score <= 2 AND f_score >= 4 THEN 'At Risk (High Value)'
		WHEN r_score <= 2 AND f_score <= 2 THEN 'Hibernating'
		WHEN r_score >= 4 AND f_score <= 2 THEN 'New Users'
		ELSE 'General'
	end AS customer_segment
FROM rfm_scores
ORDER BY ltv DESC;

COMMENT ON VIEW analytics.customer_rfm IS 'Métricas de RFM (Recency, Frequency, Monetary) e segmentação de clientes. Use para análises de LTV, churn e valor do cliente.';
COMMENT ON COLUMN analytics.customer_rfm.customer_segment IS 'Segmentação de negócio (ex: Champions, At Risk, Hibernating).';
COMMENT ON COLUMN analytics.customer_rfm.ltv_value IS 'Lifetime Value (Receita total do cliente).';
