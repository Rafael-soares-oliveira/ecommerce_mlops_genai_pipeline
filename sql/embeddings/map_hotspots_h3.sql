CREATE TABLE IF NOT EXISTS embeddings.map_hotspots_h3 AS
SELECT
    -- Todos os pontos que estão dentro de um quadrado de ~5,5km terão a mesma coordenada central
    -- Melhorar a performance
    ST_SnapToGrid(user_geom::geometry, 0.05)::geography AS grid_geom,
    COUNT(*) AS density,
    AVG(u.age)::integer AS avg_user_age
FROM raw_data.users u
GROUP BY grid_geom;
