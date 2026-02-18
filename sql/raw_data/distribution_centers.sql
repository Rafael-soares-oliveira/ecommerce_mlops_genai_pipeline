CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS raw_data.distribution_centers (
    id INTEGER PRIMARY KEY,
    name TEXT COLLATE case_insensitive NOT NULL CONSTRAINT uq_dc_name UNIQUE,
    latitude DOUBLE PRECISION CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION CHECK (longitude BETWEEN -180 AND 180),
    distribution_center_geom GEOGRAPHY(POINT, 4326) GENERATED ALWAYS AS (
        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography
    ) STORED
);
