from kedro.pipeline import Node, Pipeline

from thelook_ecommerce_analysis.pipelines.data_embeddings.nodes import (
    execute_sql_query,
    fct_user_logistics,
    generate_embeddings,
    map_hotspots_h3,
    prepare_products_for_embedding,
    prepare_users_for_embedding,
)


def create_pipeline(**kwargs) -> Pipeline:
    return Pipeline(
        [
            # Products Embedding
            Node(
                func=execute_sql_query,
                inputs={
                    "table": "primary_products",
                    "trigger_execution": "create_products_embeddings",
                },
                outputs="products_embedding_complete_flag",
                name="create_products_embedding_node",
                tags=["embedding", "products"],
            ),
            Node(
                func=prepare_products_for_embedding,
                inputs=["primary_products", "products_embedding_complete_flag"],
                outputs="prepared_products",
                name="prepare_products_chunks_node",
                tags=["embedding", "products"],
            ),
            Node(
                func=generate_embeddings,
                inputs=["prepared_products", "embedding_model"],
                outputs="products_embeddings",
                name="generate_products_embeddings_node",
                tags=["embedding", "products"],
            ),
            # Geo Search
            Node(
                func=execute_sql_query,
                inputs={
                    "table": "primary_users",
                    "trigger_execution": "create_fct_vector_geo_search",
                },
                outputs="vector_geo_search_embedding_complete_flag",
                name="create_users_embedding_node",
                tags=["embedding", "users"],
            ),
            Node(
                func=prepare_users_for_embedding,
                inputs={
                    "users": "primary_users",
                    "order_items": "primary_order_items",
                    "trigger": "vector_geo_search_embedding_complete_flag",
                },
                outputs="prepared_users",
                name="prepare_users_chunks_node",
                tags=["embedding", "users"],
            ),
            Node(
                func=generate_embeddings,
                inputs=["prepared_users", "embedding_model"],
                outputs="fct_vector_geo_search_embeddings",
                name="generate_users_embeddings_node",
                tags=["embedding", "users"],
            ),
            # Map Hotspot H3
            Node(
                func=map_hotspots_h3,
                inputs={
                    "users": "primary_users",
                    "trigger_execution": "create_map_hotpots_h3",
                },
                outputs="hotspots_complete_flag",
                name="create_map_hotspots_h3_node",
                tags=["geo"],
            ),
            # User Logistics
            Node(
                func=fct_user_logistics,
                inputs={
                    "users": "primary_users",
                    "orders": "primary_orders",
                    "order_items": "primary_order_items",
                    "products": "primary_products",
                    "distribution_centers": "primary_distribution_centers",
                    "trigger_execution": "create_fct_user_logistics",
                },
                outputs="fct_user_logistics_complete_flag",
                name="create_fct_user_logistics_node",
                tags=["geo"],
            ),
        ]
    )
