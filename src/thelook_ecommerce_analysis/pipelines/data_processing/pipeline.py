from kedro.pipeline import Node, Pipeline

from thelook_ecommerce_analysis.utils.partial_func import create_node_func

from .nodes import (
    extract_distribution_centers,
    extract_inventory_items,
    extract_order_items,
    extract_orders,
    extract_products,
    extract_users,
)
from .schema_rules import (
    distribution_centers_schema,
    inventory_items_schema,
    order_items_schema,
    orders_schema,
    products_schema,
    users_schema,
)


def create_pipeline(**kwargs) -> Pipeline:
    return Pipeline(
        [
            Node(
                func=create_node_func(extract_users, schema_rules=users_schema),
                inputs={
                    "users": "raw_users",
                    "columns": "params:tables.users.columns",
                },
                outputs="primary_users",
                name="process_users_table_node",
                tags=["raw", "users"],
            ),
            Node(
                func=create_node_func(
                    extract_distribution_centers,
                    schema_rules=distribution_centers_schema,
                ),
                inputs={
                    "dc": "raw_distribution_centers",
                    "columns": "params:tables.distribution_centers.columns",
                },
                outputs="primary_distribution_centers",
                name="process_distribution_centers_table_node",
                tags=["raw", "distribution_centers"],
            ),
            Node(
                func=create_node_func(
                    extract_products,
                    schema_rules=products_schema,
                ),
                inputs={
                    "products": "raw_products",
                    "dc": "primary_distribution_centers",
                    "columns": "params:tables.products.columns",
                },
                outputs="primary_products",
                name="process_products_table_node",
                tags=["raw", "products"],
            ),
            Node(
                func=create_node_func(
                    extract_inventory_items,
                    schema_rules=inventory_items_schema,
                ),
                inputs={
                    "ii": "raw_inventory_items",
                    "target": "primary_consult_inventory_items",
                    "dc": "primary_distribution_centers",
                    "columns": "params:tables.inventory_items.columns",
                },
                outputs="primary_inventory_items",
                name="process_inventory_items_table_node",
                tags=["raw", "inventory_items"],
            ),
            Node(
                func=create_node_func(
                    extract_orders,
                    schema_rules=orders_schema,
                ),
                inputs={
                    "orders": "raw_orders",
                    "users": "primary_users",
                    "lookback": "params:order_lookback_days",
                    "columns": "params:tables.orders.columns",
                },
                outputs="primary_orders",
                name="process_orders_table_node",
                tags=["raw", "orders"],
            ),
            Node(
                func=create_node_func(
                    extract_order_items,
                    schema_rules=order_items_schema,
                ),
                inputs={
                    "order_items": "raw_order_items",
                    "orders": "primary_orders",
                    "users": "primary_users",
                    "products": "primary_products",
                    "inv_items": "primary_inventory_items",
                    "lookback": "params:order_lookback_days",
                    "columns": "params:tables.order_items.columns",
                },
                outputs="primary_order_items",
                name="process_order_items_table_node",
                tags=["raw", "order_items"],
            ),
        ],
        namespace="data_processing",
        prefix_datasets_with_namespace=False,
    )
