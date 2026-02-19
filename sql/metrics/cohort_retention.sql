WITH user_cohorts AS (
	SELECT
		oi.user_id,
		u.country,
		DATE_TRUNC('month', MIN(oi.created_at))::date AS cohort_month
	FROM raw_data.order_items oi
	JOIN raw_data.users u ON oi.user_id = u.id
	WHERE oi.status NOT IN ('Cancelled', 'Returned')
	GROUP BY 1, 2
),
user_activities AS (
	SELECT
		oi.user_id,
		DATE_TRUNC('month', oi.created_at)::date AS activity_month
	FROM raw_data.order_items oi
	WHERE oi.status NOT IN ('Cancelled', 'Returned')
	GROUP BY 1, 2
),
cohort_base AS (
	SELECT
		uc.country,
		uc.cohort_month,
		ua.activity_month,
		COUNT(DISTINCT uc.user_id) AS active_users,
		(
			EXTRACT(year FROM AGE(ua.activity_month, uc.cohort_month)) * 12 + EXTRACT(month FROM AGE(ua.activity_month, uc.cohort_month))
		) AS month_number
	FROM user_cohorts uc
	JOIN user_activities ua ON uc.user_id = ua.user_id
	GROUP BY 1, 2, 3
),
cohort_size AS (
	SELECT
		country,
		cohort_month,
		COUNT(DISTINCT user_id) AS original_users
	FROM user_cohorts
	GROUP BY 1, 2
)
SELECT
	b.country,
	b.cohort_month,
	s.original_users,
	b.month_number,
	b.active_users,
	ROUND((b.active_users::numeric / s.original_users) * 100, 2) AS retention_rate
FROM cohort_base b
JOIN cohort_size s ON b.cohort_month = s.cohort_month AND b.country = s.country
WHERE b.month_number <= 12
ORDER BY 1, 2, 4;


COMMENT ON VIEW analytics.cohort_retention IS 'Análise de retenção de clientes por safra (cohort) e país. Use para analisar o engajamento ao longo dos meses.';
COMMENT ON COLUMN analytics.cohort_retention.month_number IS 'Mês de vida da safra (0 é o mês da primeira compra, 1 é o mês seguinte, etc).';
COMMENT ON COLUMN analytics.cohort_retention.retention_rate IS 'Taxa percentual de retenção (0 a 100).';
