CREATE TABLE IF NOT EXISTS raw_data.inventory_items (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    sold_at TIMESTAMP WITH TIME ZONE,
    cost NUMERIC(10, 2) NOT NULL CHECK (cost >= 0),
    product_category TEXT NOT NULL COLLATE case_insensitive,
    product_name TEXT NOT NULL COLLATE case_insensitive,
    product_brand TEXT NOT NULL COLLATE case_insensitive,
    product_retail_price NUMERIC(10, 2) NOT NULL CHECK (product_retail_price >= 0),
    product_department TEXT NOT NULL COLLATE case_insensitive,
    product_sku TEXT NOT NULL,
    product_distribution_center_id INTEGER NOT NULL,

    CONSTRAINT check_sold_after_created_inv CHECK (sold_at >= created_at),

    CONSTRAINT fk_inventory_distribution FOREIGN KEY (product_distribution_center_id) REFERENCES raw_data.distribution_centers (id)
);
