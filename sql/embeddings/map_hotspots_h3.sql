CREATE TABLE IF NOT EXISTS embeddings.map_hotspots_h3 AS
SELECT
    -- Todos os pontos que estão dentro de um quadrado de ~5,5km terão a mesma coordenada central
    -- Melhorar a performance
    ST_SnapToGrid(user_geom::geometry, 0.05)::geography AS grid_geom,
    COUNT(*) AS density,
    AVG(u.age)::integer AS avg_user_age
FROM raw_data.users u
GROUP BY grid_geom;

-- Comentários para map_hotspots_h3
COMMENT ON TABLE embeddings.map_hotspots_h3 IS 'View materializada de mapa de calor. Agrupa usuários em grids espaciais de 5,5km. Use para análises de densidade e concentração territorial.';
COMMENT ON COLUMN embeddings.map_hotspots_h3.grid_geom IS 'Coordenada central do quadrante de concentração.';
COMMENT ON COLUMN embeddings.map_hotspots_h3.density IS 'Número total de usuários morando neste quadrante.';
