CREATE TABLE IF NOT EXISTS raw_data.products (
    id INTEGER PRIMARY KEY,
    cost NUMERIC(10, 2) NOT NULL CHECK (cost > 0),
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    retail_price NUMERIC(10, 2) NOT NULL CHECK (retail_price >= 0),
    department TEXT NOT NULL,
    sku TEXT NOT NULL,
    distribution_center_id SMALLINT NOT NULL,

    CONSTRAINT fk_products_distribution_centers FOREIGN KEY (distribution_center_id) REFERENCES raw_data.distribution_centers (id)
);
