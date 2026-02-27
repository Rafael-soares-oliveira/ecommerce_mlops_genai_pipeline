from typing import Any

from kedro.pipeline import Node, Pipeline

from thelook_ecommerce_analysis.pipelines.data_metrics.nodes import (
    create_metrics_tables,
)
from thelook_ecommerce_analysis.utils.partial_func import create_node_func

from .metrics.customer_metrics import cohort_retention, customer_rfm_ltv
from .metrics.product_360 import product_360
from .metrics.sales_daily import daily_sales_and_revenue
from .metrics.web_analytics import (
    sales_funnel,
    session_conversion,
    traffic_source_performance,
)


def create_pipeline(**kwargs) -> Pipeline:
    metrics_config: list[dict[str, Any]] = [
        {
            "func": daily_sales_and_revenue,
            "inputs": {
                "order_items": "primary_order_items",
                "products": "primary_products",
                "users": "primary_users",
                "returns_cost": "params:metrics.returns_cost",
            },
            "outputs": "metrics_sales_daily",
        },
        {
            "func": customer_rfm_ltv,
            "inputs": {
                "users": "primary_users",
                "order_items": "primary_order_items",
            },
            "outputs": "metrics_customer_rfm_ltv",
        },
        {
            "func": cohort_retention,
            "inputs": {
                "users": "primary_users",
                "order_items": "primary_order_items",
                "month_limit": "params:metrics.cohort_limit",
            },
            "outputs": "metrics_cohort_retention",
        },
        {
            "func": product_360,
            "inputs": {
                "order_items": "primary_order_items",
                "products": "primary_products",
                "inventory_items": "primary_inventory_items",
            },
            "outputs": "metrics_products_performance",
        },
        {
            "func": session_conversion,
            "inputs": {
                "events": "primary_events",
            },
            "outputs": "metrics_session_conversion",
        },
        {
            "func": traffic_source_performance,
            "inputs": {
                "users": "primary_users",
                "orders": "primary_orders",
                "order_items": "primary_order_items",
            },
            "outputs": "metrics_traffic_source_performance",
        },
        {
            "func": sales_funnel,
            "inputs": {"events": "primary_events"},
            "outputs": "metrics_sales_funnel",
        },
    ]

    nodes = []

    for config in metrics_config:
        node_func = create_node_func(create_metrics_tables, fun=config["func"])

        nodes.append(
            Node(
                func=node_func,
                inputs=config["inputs"],
                outputs=config["outputs"],
                name=f"node_{config['outputs']}",
                tags=["metrics", node_func.__name__],
            )
        )

    return Pipeline(nodes)
