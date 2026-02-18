from decimal import Decimal

import ibis
import pandas as pd

from thelook_ecommerce_analysis.pipelines.data_processing.transform_tables import (
    transform_distribution_centers,
    transform_inventory_items,
    transform_order_items,
    transform_orders,
    transform_products,
)


class TestTransformTables:
    """Suíte de testes dedicada às regras puras de transformação Ibis."""

    def test_transform_distribution_centers(self) -> None:
        """Valida clip de coordenadas e cast de ID."""
        df = pd.DataFrame({"id": ["1"], "latitude": [100.0], "longitude": [-200.0]})
        table = transform_distribution_centers(ibis.memtable(df))
        res = table.to_pandas()

        assert res["id"].dtype == "int32", "O dtype de 'id' deveria ser 'int32'"
        assert res["latitude"].iloc[0] == 90.0, "Latitude 100 deveria virar 90"
        assert res["longitude"].iloc[0] == -180.0, "Longitude -180 deveria virar 180"

    def test_transform_products(self) -> None:
        """Valida tratamento de nulos, valores monetários absolutos e tipagem."""
        df = pd.DataFrame(
            {
                "id": ["1"],
                "cost": [-50.555],
                "category": [None],
                "name": [None],
                "brand": [None],
                "retail_price": [-100.999],
                "department": [None],
                "sku": [None],
                "distribution_center_id": ["2"],
            }
        )
        table = transform_products(ibis.memtable(df))
        res = table.to_pandas()

        assert res["cost"].iloc[0] == Decimal("50.56"), (
            "O valor de 'cost' -50.555 deveria virar positivo e arredondado para 50.56"
        )
        assert res["retail_price"].iloc[0] == 101.00, (
            "O valor de 'retail_price' -100.999 deveria virar positivo e arredondado para 101.00"
        )
        assert res["category"].iloc[0] == "Unknown", (
            "Valor nulo de 'category' deveria virar 'Unknown'"
        )

    def test_transform_inventory_items(self) -> None:
        """Valida regras de nulos e cast temporal do inventário."""
        df = pd.DataFrame(
            {
                "id": ["1"],
                "product_id": ["10"],
                "created_at": ["2023-01-01T00:00:00"],
                "sold_at": [None],
                "cost": [-10.0],
                "product_category": [None],
                "product_name": [None],
                "product_brand": [None],
                "product_retail_price": ["20.0"],
                "product_department": [None],
                "product_sku": [None],
                "product_distribution_center_id": ["2"],
            }
        )

        table = transform_inventory_items(ibis.memtable(df))
        res = table.to_pandas()

        assert pd.api.types.is_datetime64_any_dtype(res["created_at"]), (
            "dtype da coluna 'created_at' deveria ser datetime"
        )
        assert res["product_brand"].iloc[0] == "Unknown", (
            "Valor nulo da coluna 'product_brand' deveria ser 'Unknown'"
        )
        assert res["cost"].iloc[0] == 10.0, (
            "Valor da coluna 'cost' -10.0 deveria ser positivo"
        )

    def test_transform_orders_and_items_temporal_logic(self) -> None:
        """Valida as lógicas críticas temporais (shipped não pode ser antes de created_at, etc."""
        df = pd.DataFrame(
            {
                "order_id": ["1"],
                "user_id": ["1"],
                "num_of_item": ["2"],
                "created_at": ["2023-01-05"],
                "shipped_at": ["2023-01-01"],  # Inválido: Shipped antes de created
                "delivered_at": [
                    "2023-01-04"
                ],  # Inválido: Delivered antes de shipped corrigido
                "returned_at": [
                    "2023-01-04"
                ],  # Inválido: Returned antes de delivered corrigido
            }
        )

        # Testando Orders
        table_orders = transform_orders(ibis.memtable(df))
        res_orders = table_orders.to_pandas()

        assert res_orders["shipped_at"].iloc[0] == pd.Timestamp("2023-01-05"), (
            "'shipped_at' é menor que 'created_at', então deveria ter assumido o valor de created_at"
        )

        # Testando Order Items
        df_items = df.copy()
        df_items["id"] = ["1"]
        df_items["product_id"] = ["1"]
        df_items["inventory_item_id"] = ["1"]
        df_items["status"] = [None]
        df_items["sale_price"] = ["10.0"]

        table_items = transform_order_items(ibis.memtable(df_items))
        res_items = table_items.to_pandas()

        assert res_items["status"].iloc[0] == "Processing", (
            "Valores nulos da coluna 'status' deveriam ser 'Processing'"
        )
        assert res_items["shipped_at"].iloc[0] == pd.Timestamp("2023-01-05"), (
            "Deveria ser um Timestamp"
        )
