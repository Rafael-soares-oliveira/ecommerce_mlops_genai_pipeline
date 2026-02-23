from decimal import Decimal

import ibis
import pandas as pd

from thelook_ecommerce_analysis.pipelines.data_processing.transform_tables import (
    transform_distribution_centers,
    transform_events,
    transform_inventory_items,
    transform_order_items,
    transform_orders,
    transform_products,
    transform_users,
)


class TestTransformTables:
    """Suíte de testes dedicada às regras puras de transformação Ibis."""

    def test_transform_users(self) -> None:
        """Valida tipagem, clip de coordenadas e criação do context_sumamry."""
        df = pd.DataFrame(
            {
                "id": ["1"],
                "age": [-25],
                "gender": [None],
                "state": [None],
                "city": [None],
                "country": [None],
                "traffic_source": ["Organic"],
                "latitude": [100.0],
                "longitude": [-200.0],
            }
        )

        table = transform_users(ibis.memtable(df))
        res = table.to_pandas()

        assert res["age"].iloc[0] == 25, (
            "Idade negativa deveria ser convertida para positiva"
        )
        assert res["latitude"].iloc[0] == 90.0, (
            "Latitude 100 deveria ser clipada para 90"
        )
        assert res["longitude"].iloc[0] == -180.0, (
            "Longitude -200 deveria ser clipada para -180"
        )
        assert res["gender"].iloc[0] == "Others", "Gender nulo deveria virar 'Others'"
        assert "User profile:" in res["context_summary"].iloc[0], (
            "Summary deve conter o prefixo esperado"
        )
        assert "25 years old" in res["context_summary"].iloc[0], (
            "Summary deve conter a idade tratada"
        )

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
        assert res["retail_price"].iloc[0] == Decimal("101.00"), (
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
        assert res["cost"].iloc[0] == Decimal("10.0"), (
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

    def test_transform_events(self) -> None:
        """Valida tipagem, tratamento de nulos e inferência de visitor_type."""
        df = pd.DataFrame(
            {
                "id": ["1", "2", "3"],
                "user_id": [10, None, None],  # Testa lógica do visitor_type
                "sequence_number": [1, 2, 1],
                "created_at": ["2023-01-01T00:00:00"] * 3,
                "session_id": ["sess1", "sess1", "sess2"],
                "city": [None, "City", None],
                "state": [None, "State", None],
                "browser": [None, "Chrome", None],
                "traffic_source": [None, "Organic", None],
                "uri": ["/product/123/", "/category/shoes", None],
                "event_type": [None, "product", None],
            }
        )
        table = transform_events(ibis.memtable(df))
        res = table.to_pandas().sort_values("id").reset_index(drop=True)

        assert res["visitor_type"].iloc[0] == "Registered", (
            "user_id preenchido deve ser Registered"
        )
        assert res["extracted_product_id"].iloc[0] == 123, (
            "Regex deveria extrair o ID 123 da URI"
        )
        assert res["extracted_page_type"].iloc[0] == "product", (
            "Split deveria extrair a page_type"
        )

        # Validação do Evento 2 (Mesma sessão, Window Function propaga o ID 10)
        assert res["user_id"].iloc[1] == 10, (
            "A Window Function deveria preencher o ID nulo com 10"
        )
        assert res["visitor_type"].iloc[1] == "Registered", (
            "Deveria inferir Registered por conta do Window"
        )
        assert res["extracted_page_type"].iloc[1] == "category", (
            "Split deveria pegar a categoria limpa"
        )

        # Validação do Evento 3 (Sessão diferente, sem ID de usuário)
        assert res["visitor_type"].iloc[2] == "Guest", (
            "Sessão puramente nula deve ser Guest"
        )
        assert pd.isna(res["extracted_product_id"].iloc[2]), (
            "URI Nula não deve quebrar o regex"
        )
