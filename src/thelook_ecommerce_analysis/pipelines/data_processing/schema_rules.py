"""
Validação dos dados que serão injetados no Banco de Dados para atender scripts SQL para criação das tabelas.
"""

users_schema = {
    # Regras de linha - Retorna Boolean
    "row": {
        "id_missing": lambda t: t["id"].isnull(),
        "age_invalid": lambda t: t["age"] < 0,
        "gender_invalid": lambda t: ~t["gender"].isin(["M", "F", "Others"]),
        "lat_out_range": lambda t: ~t["latitude"].between(-90, 90),
        "lon_out_range": lambda t: ~t["longitude"].between(-180, 180),
        "created_missing": lambda t: t["created_at"].isnull(),
    },
    # Regras de agregação - Retorna Escalar
    "agg": {"id_duplicated": lambda t: t.count() - t["id"].nunique()},
}

distribution_centers_schema = {
    "row": {
        "id_missing": lambda t: t["id"].isnull(),
        "name_missing": lambda t: t["name"].isnull(),
        "lat_out_range": lambda t: ~t["latitude"].between(-90, 90),
        "lon_out_range": lambda t: ~t["longitude"].between(-180, 180),
    },
    "agg": {
        "id_duplicated": lambda t: t.count() - t["id"].nunique(),
        "name_duplicates": lambda t: t.count() - t["name"].lower().nunique(),
    },
}

products_schema = {
    "row": {
        "id_missing": lambda t: t["id"].isnull(),
        "cost_missing": lambda t: t["cost"].isnull(),
        "cost_negative": lambda t: t["cost"] <= 0,
        "price_missing": lambda t: t["retail_price"].isnull(),
        "price_negative": lambda t: t["retail_price"] < 0,
        "sku_missing": lambda t: t["sku"].isnull(),
        # "dept_missing": lambda t: t["department"].notnull(),
    },
    "agg": {
        "id_duplicated": lambda t: t.count() - t["id"].nunique(),
        "sku_duplicated": lambda t: t.count() - t["sku"].nunique(),
    },
}

inventory_items_schema = {
    "row": {
        # --- Missing IDs ---
        "id_missing": lambda t: t["id"].isnull(),
        "prod_id_missing": lambda t: t["product_id"].isnull(),
        "dist_center_missing": lambda t: t["product_distribution_center_id"].isnull(),
        "created_missing": lambda t: t["created_at"].isnull(),
        # --- Constraint Check ---
        # se sold_at não for null e for maior que created_at
        "sold_data_invalid": lambda t: (
            t["sold_at"].notnull() & (t["sold_at"] < t["created_at"])
        ),
        # --- Valores Monetários ---
        "cost_missing": lambda t: t["cost"].isnull(),
        "cost_negative": lambda t: t["cost"] < 0,
        "price_missing": lambda t: t["product_retail_price"].isnull(),
        "price_negative": lambda t: t["product_retail_price"] < 0,
        # --- Strings Obrigatórias ---
        "category_missing": lambda t: t["product_category"].isnull(),
        "name_missing": lambda t: t["product_name"].isnull(),
        "brand_missing": lambda t: t["product_brand"].isnull(),
        "dept_missing": lambda t: t["product_department"].isnull(),
        "sku_missing": lambda t: t["product_sku"].isnull(),
    },
    "agg": {"id_duplicated": lambda t: t.count() - t["id"].nunique()},
}

orders_schema = {
    "row": {
        # Missing IDs e Status
        "id_missing": lambda t: t["order_id"].isnull(),
        "user_id_missing": lambda t: t["user_id"].isnull(),
        "status_missing": lambda t: t["status"].isnull(),
        # CHECK
        "status_invalid": lambda t: (
            t["status"].notnull()
            & ~t["status"].isin(
                ["Processing", "Shipped", "Complete", "Returned", "Cancelled"]
            )
        ),
        # Quantidade de Itens
        "items_missing": lambda t: t["num_of_item"].isnull(),
        "items_invalid": lambda t: t["num_of_item"] <= 0,
        # Validação Temporal
        # 1. created_at not null
        "created_missing": lambda t: t["created_at"].isnull(),
        # 2. shipped_at >= created_at
        "ship_early_err": lambda t: (
            t["shipped_at"].notnull() & (t["shipped_at"] < t["created_at"])
        ),
        # 3. delivered_at >= shipped_at e ambos existem
        "delivered_early_err": lambda t: (
            t["delivered_at"].notnull()
            & t["shipped_at"].notnull()
            & (t["delivered_at"] < t["shipped_at"])
        ),
        # 4. returned_at >= delivered_at e ambos existe
        "returned_early_err": lambda t: (
            t["returned_at"].notnull()
            & t["delivered_at"].notnull()
            & (t["returned_at"] < t["delivered_at"])
        ),
    },
    "agg": {"id_duplicated": lambda t: t.count() - t["order_id"].nunique()},
}

order_items_schema = {
    "row": {
        # Missing IDs
        "id_missing": lambda t: t["id"].isnull(),
        "order_id_missing": lambda t: t["order_id"].isnull(),
        "user_id_missing": lambda t: t["user_id"].isnull(),
        "prod_id_missing": lambda t: t["product_id"].isnull(),
        "inv_id_missing": lambda t: t["inventory_item_id"].isnull(),
        # Status
        "status_invalid": lambda t: (
            t["status"].notnull()
            & ~t["status"].isin(
                ["Processing", "Shipped", "Complete", "Returned", "Cancelled"]
            )
        ),
        # Sale Price
        "price_negative": lambda t: t["sale_price"].notnull() & (t["sale_price"] < 0),
        # Validação Temporal
        # 1. created_at not null
        "created_missing": lambda t: t["created_at"].isnull(),
        # 2. shipped_at >= created_at
        "ship_early_err": lambda t: (
            t["shipped_at"].notnull() & (t["shipped_at"] < t["created_at"])
        ),
        # 3. delivered_at >= shipped_at e ambos existem
        "delivered_early_err": lambda t: (
            t["delivered_at"].notnull()
            & t["shipped_at"].notnull()
            & (t["delivered_at"] < t["shipped_at"])
        ),
        # 4. returned_at >= delivered_at e ambos existe
        "returned_early_err": lambda t: (
            t["returned_at"].notnull()
            & t["delivered_at"].notnull()
            & (t["returned_at"] < t["delivered_at"])
        ),
    },
    "agg": {"id_duplicated": lambda t: t.count() - t["id"].nunique()},
}
