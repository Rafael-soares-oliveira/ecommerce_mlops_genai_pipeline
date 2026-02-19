CREATE TABLE IF NOT EXISTS embeddings.fct_user_logistics AS
SELECT
    u.id AS user_id,
    dc.id AS dc_id,
    u.user_geom,
    dc.distribution_center_geom,
    round(ST_Distance(u.user_geom, dc.distribution_center_geom)::numeric / 1000, 3) AS distance_km
FROM raw_data.users u
JOIN raw_data.orders o ON u.id = o.user_id
JOIN raw_data.order_items oi ON o.order_id = oi.order_id
JOIN raw_data.products p ON oi.product_id = p.id
JOIN raw_data.distribution_centers dc ON p.distribution_center_id = dc.id;

-- Comentários para fct_user_logistics
COMMENT ON TABLE embeddings.fct_user_logistics IS 'Tabela de fatos logísticos com distâncias pré-calculadas entre usuários e CDs baseadas em pedidos reais.';
COMMENT ON COLUMN embeddings.fct_user_logistics.distance_km IS 'Distância exata em quilômetros. Use esta coluna em vez de recalcular com ST_Distance.';
