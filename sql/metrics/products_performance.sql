/*
WITH sales_metrics AS (
    SELECT
        oi.product_id,
        EXTRACT(YEAR FROM oi.created_at) AS sales_year,
        COUNT(oi.id) AS total_units_sold,
        SUM(oi.sale_price) AS total_revenue,
        COUNT(CASE WHEN oi.status = 'Returned' THEN 1 END) AS total_returned_units,
        (COUNT(CASE WHEN oi.status = 'Returned' THEN 1 END)::numeric /
         NULLIF(COUNT(CASE WHEN oi.status IN ('Complete', 'Returned', 'Shipped') THEN 1 END), 0)) AS return_rate,
        AVG(EXTRACT(epoch FROM (oi.shipped_at - oi.created_at))/86400) AS avg_to_shipping_days,
        AVG(oi.sale_price) AS aov,
        CURRENT_DATE - MAX(oi.created_at)::date AS days_since_last_sale
    FROM raw_data.order_items oi
    WHERE oi.status NOT IN ('Cancelled') AND oi.created_at IS NOT NULL
    GROUP BY 1, 2
),
inventory_stats AS (
    SELECT
        ii.product_id,
        COUNT(ii.sold_at)::numeric / NULLIF(COUNT(CASE WHEN ii.sold_at IS NULL THEN 1 END), 0) AS turnover_ratio,
        AVG(ii.sold_at::date - ii.created_at::date) AS avg_days_to_sell,
        COUNT(CASE WHEN ii.sold_at IS NULL THEN 1 END) AS current_stock
    FROM raw_data.inventory_items ii
    GROUP BY 1
)
SELECT
    p.id AS product_id,
    sa.sales_year,
    p.category,
    p.name AS product_name,
    -- Volumes
    sa.total_units_sold,
    ROUND(sa.total_revenue::numeric, 2) AS total_revenue,
    -- Tempos
    ROUND(sa.avg_to_shipping_days::numeric, 1) as avg_shipping_days,
    sa.days_since_last_sale,
    COALESCE(st.current_stock, 0) AS stock_qt,
    -- Giro
    ROUND(st.turnover_ratio, 2) AS inventory_turnover,
    ROUND(st.avg_days_to_sell, 2) AS avg_days_to_sell,
    -- Rentabilidade/Operação
    ROUND(sa.return_rate * 100, 2) AS return_rate_pct,
    ROUND(((sa.aov - p.cost) / NULLIF(sa.aov, 0)) * 100, 2) AS avg_margin_pct,
    ROUND(sa.aov::numeric, 2) AS aov
FROM raw_data.products p
JOIN sales_metrics sa ON p.id = sa.product_id
LEFT JOIN inventory_stats st ON p.id = st.product_id
ORDER BY sa.sales_year DESC, total_revenue DESC;
*/
