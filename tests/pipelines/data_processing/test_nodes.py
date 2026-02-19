import logging

import ibis
import pandas as pd
import pytest
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis.pipelines.data_processing.nodes import (
    _validate_ibis_table,
    extract_distribution_centers,
    extract_events,
    extract_inventory_items,
    extract_order_items,
    extract_orders,
    extract_products,
    extract_users,
)
from thelook_ecommerce_analysis.pipelines.data_processing.schema_rules import (
    distribution_centers_schema,
    events_schema,
    inventory_items_schema,
    order_items_schema,
    orders_schema,
    products_schema,
    users_schema,
)


class TestDataProcessingNodes:
    """Suíte de testes para os nós de processamento e validação Ibis."""

    @pytest.fixture
    def raw_users_table(self) -> ibis.Table:
        """Fixture que cria uma tabela Ibis virtual com dados brutos de usuários."""
        df = pd.DataFrame(
            {
                "id": [1, 2, 3],
                "age": [
                    25,
                    -10,
                    None,
                ],  # -10 e None são inválidos nas regras e precisam do transform
                "gender": ["M", "F", None],
                "state": ["SP", "RJ", None],
                "city": ["São Paulo", "Rio", None],
                "country": ["Brazil", "Brazil", None],
                "traffic_source": ["Organic", "Facebook", None],
                "latitude": [10.0, -15.0, 200.0],  # 200 é fora do range
                "longitude": [20.0, -30.0, -200.0],  # -200 é fora do range
                "created_at": ["2023-01-01", "2023-01-02", "2023-01-03"],
            }
        )
        return ibis.memtable(df)

    def test_validate_ibis_table_sucess(self) -> None:
        """Garante que dados válidos passem pelo validador do schema sem erros."""
        valid_df = pd.DataFrame(
            {
                "id": [1, 2],
                "age": [25, 30],
                "gender": ["M", "F"],
                "latitude": [10.0, -10.0],
                "longitude": [20.0, -20.0],
                "created_at": ["2023-01-01", "2023-01-02"],
            }
        )
        valid_table = ibis.memtable(valid_df)

        result = _validate_ibis_table(valid_table, users_schema)
        assert result is not None

    def test_validate_ibis_table_failure(self) -> None:
        """Garante que a violação de regras de schema levante ValueError."""
        invalid_df = pd.DataFrame(
            {
                "id": [1, 1],
                "age": [-5, 30],
                "gender": ["X", "F"],
                "latitude": [100.0, -10.0],
                "longitude": [20.0, -20.0],
                "created_at": ["2023-01-01", "2023-01-02"],
            }
        )
        invalid_table = ibis.memtable(invalid_df)

        with pytest.raises(ValueError) as excinfo:
            _validate_ibis_table(invalid_table, users_schema)

        assert "Violação de Contrato Ibis detectada" in str(excinfo.value)
        assert "age_invalid" in str(excinfo.value)
        assert "id_duplicated" in str(excinfo.value)

    def test_extract_users_transformation(self, raw_users_table: ibis.Table) -> None:
        """Verifica se o node extract_users aplica as tipagens e limpezas corretas."""
        cols = [
            "id",
            "age",
            "gender",
            "state",
            "city",
            "country",
            "traffic_source",
            "latitude",
            "longitude",
            "created_at",
        ]

        result_table = extract_users(raw_users_table, users_schema, cols)
        result_df = result_table.to_pandas()

        assert result_df.loc[result_df["id"] == 2, "age"].iloc[0] == 10, (
            "Age 10 deveria virar 10 (abs)"
        )
        assert result_df.loc[result_df["id"] == 3, "age"].iloc[0] == 0, (
            "None deveria virar 0"
        )
        assert result_df.loc[result_df["id"] == 3, "latitude"].iloc[0] == 90.0, (
            "Latitude 200 deveria ser clipada para 90"
        )
        assert "context_summary" in result_df.columns, (
            "Deveria existir a coluna 'context_summary'"
        )

    def test_extract_products_fk_violation(self, mocker: MockerFixture) -> None:
        """Valida o comportamento de Integridade Referencial (Anti-join e Semi-join). Garante que produtos órfãos são descartados e o alerta é logado."""
        spy_logger = mocker.spy(
            logging.getLogger(
                "thelook_ecommerce_analysis.pipelines.data_processing.nodes"
            ),
            "warning",
        )

        products_df = pd.DataFrame(
            {
                "id": [101, 102],
                "cost": [10.0, 15.0],
                "category": ["A", "B"],
                "name": ["Prod1", "Prod2"],
                "brand": ["BrandX", "BrandY"],
                "retail_price": [20.0, 30.0],
                "department": ["Dept1", "Dept2"],
                "sku": ["SKU1", "SKU2"],
                "distribution_center_id": [1, 999],  # 999 é órfão
            }
        )

        dc_df = pd.DataFrame({"id": [1], "latitude": [0.0], "longitude": [0.0]})

        products_table = ibis.memtable(products_df)
        dc_table = ibis.memtable(dc_df)
        cols = [
            "id",
            "cost",
            "category",
            "name",
            "brand",
            "retail_price",
            "department",
            "sku",
            "distribution_center_id",
        ]

        result = extract_products(products_table, dc_table, products_schema, cols)
        res_df = result.to_pandas()

        assert len(res_df) == 1, "O produto 102 (DC 999) deve ser dropado"
        assert res_df["id"].iloc[0] == 101, "Primeiro registro deve ter id igual a 101"

        # Garante que o warning de integridade foi disparado para o dev/ops
        spy_logger.assert_called_once()
        assert "INTEGRIDADE REFERENCIAL" in spy_logger.call_args[0][0]

    def test_validate_ibis_table_no_metrics(self) -> None:
        """Testa o Early Exit, levanta erro se não tiver métricas."""
        df = pd.DataFrame({"id": [1]})
        table = ibis.memtable(df)

        with pytest.raises(
            ValueError,
            match="Regras do Schema da tabela não pode estar vazio.",
        ):
            _validate_ibis_table(table, rules={})

    def test_extract_products_exception_handling(self, mocker: MockerFixture) -> None:
        """Garante que falhas de banco de dados no carregamento da FK levantam exceção e logam erro."""
        products_df = pd.DataFrame(
            {
                "id": [1],
                "cost": [10.0],
                "category": ["A"],
                "name": ["N"],
                "brand": ["B"],
                "retail_price": [20.0],
                "department": ["D"],
                "sku": ["S"],
                "distribution_center_id": [1],
            }
        )
        products_table = ibis.memtable(products_df)
        cols = list(products_df.columns)

        # Mock da função dc.select()
        # Simular a queda do banco de dados na chamada do select()
        dc_mock = mocker.Mock()
        dc_mock.select.side_effect = Exception("DB Connection Lost")

        # Espionamos o logger para garantir que o erro não passa silencioso
        spy_logger = mocker.spy(
            logging.getLogger(
                "thelook_ecommerce_analysis.pipelines.data_processing.nodes"
            ),
            "error",
        )

        with pytest.raises(Exception, match="DB Connection Lost"):
            extract_products(
                products=products_table, dc=dc_mock, schema_rules={}, columns=cols
            )

        spy_logger.assert_called_once()
        assert "Erro ao ler distribution_centers" in spy_logger.call_args[0][0]

    def test_extract_inventory_items_incremental_empty(
        self, mocker: MockerFixture
    ) -> None:
        """Testa o early return de limite de dados (row_count==0) na lógica incremental."""
        # Dados velhos
        ii_df = pd.DataFrame(
            {
                "id": [1],
                "product_id": [1],
                "created_at": pd.to_datetime(["2023-01-01"], utc=True),
                "sold_at": [None],
                "cost": [10],
                "product_category": ["A"],
                "product_name": ["A"],
                "product_brand": ["A"],
                "product_retail_price": [20],
                "product_department": ["A"],
                "product_sku": ["A"],
                "product_distribution_center_id": [1],
            }
        )

        # Target já tem dados mais novos
        target_df = pd.DataFrame(
            {"created_at": pd.to_datetime(["2023-01-05"], utc=True)}
        )
        dc_df = pd.DataFrame({"id": [1]})

        ii_table = ibis.memtable(ii_df)
        target_table = ibis.memtable(target_df)
        dc_table = ibis.memtable(dc_df)

        cols = list(ii_df.columns)
        res = extract_inventory_items(
            ii_table, target_table, dc_table, inventory_items_schema, cols
        )

        assert res.count().to_pandas() == 0, "Deve retornar uma tabela vazia"

    def test_extract_orders_lookback_empty(self, mocker: MockerFixture) -> None:
        """Testa 'lookback window' para Orders vazia."""
        orders_df = pd.DataFrame(
            {
                "order_id": [1],
                "user_id": [1],
                "created_at": pd.to_datetime(["2020-01-01"], utc=True),
                "shipped_at": pd.to_datetime(["2020-01-02"], utc=True),
                "delivered_at": pd.to_datetime(["2020-01-03"], utc=True),
                "returned_at": pd.to_datetime(["2020-01-04"], utc=True),
                "num_of_item": [1],
            }
        )
        orders_table = ibis.memtable(orders_df)
        users_table = ibis.memtable(pd.DataFrame({"id": [1]}))

        # Mock datetime
        mock_datetime = mocker.patch(
            "thelook_ecommerce_analysis.pipelines.data_processing.nodes.datetime_"
        )
        mock_datetime.now.return_value = pd.Timestamp("2023-01-01", tz="UTC")

        res = extract_orders(
            orders_table,
            users_table,
            lookback=30,
            schema_rules=orders_schema,
            columns=list(orders_df.columns),
        )

        assert res.count().to_pandas() == 0, "Deveria retornar um DataFrame vazio"

    def test_extract_order_items_happy_path(self, mocker: MockerFixture) -> None:
        """Testa a extração e validação de FK para Order Items"""
        items_df = pd.DataFrame(
            {
                "id": [1],
                "order_id": [1],
                "user_id": [1],
                "product_id": [1],
                "inventory_item_id": [1],
                "status": ["Processing"],
                "created_at": pd.to_datetime(["2023-01-01"], utc=True),
                "shipped_at": pd.to_datetime([None]),
                "delivered_at": pd.to_datetime([None]),
                "returned_at": pd.to_datetime([None]),
                "sale_price": [10.0],
            }
        )

        # Tabelas de referência para os semi-join
        items_table = ibis.memtable(items_df)
        orders_table = ibis.memtable(pd.DataFrame({"order_id": [1]}))
        users_table = ibis.memtable(pd.DataFrame({"id": [1]}))
        products_table = ibis.memtable(pd.DataFrame({"id": [1]}))
        inv_table = ibis.memtable(pd.DataFrame({"id": [1]}))

        # Mock de data para garantir que o item caia na janela
        mock_datetime = mocker.patch(
            "thelook_ecommerce_analysis.pipelines.data_processing.nodes.datetime_"
        )
        mock_datetime.now.return_value = pd.Timestamp("2023-01-05", tz="UTC")

        # Act
        res = extract_order_items(
            items_table,
            orders_table,
            users_table,
            products_table,
            inv_table,
            lookback=10,
            schema_rules=order_items_schema,
            columns=list(items_df.columns),
        )

        # Assert - 1 item passou limpo por todos os joins e transforms
        assert res.count().to_pandas() == 1, "Deveria retornar um DataFrame de 1 linha"

    def test_extract_distribution_centers_happy_path(self) -> None:
        """Testa a extração e transformação básica da tabela de distribution_centers."""
        df = pd.DataFrame(
            {"id": [1], "name": ["DC Test"], "latitude": [10.0], "longitude": [20.0]}
        )
        table = ibis.memtable(df)
        cols = list(df.columns)

        res = extract_distribution_centers(
            table, schema_rules=distribution_centers_schema, columns=cols
        )

        assert res.count().to_pandas() == 1, (
            "Deveria retornar um DataFrame com 1 registro"
        )
        assert res.to_pandas()["id"].dtype == "int32", (
            "dtype da coluna 'id' deveria ser 'int32'"
        )

    def test_extract_inventory_items_full_load(self, mocker: MockerFixture) -> None:
        """
        Testa:
        1. A exceção de Carga Full (quando a tabela target falha ao retornar max_date).
        2. O fluxo completo de semi-join/anti-join com produtos órfãos.
        """
        spy_logger = mocker.spy(
            logging.getLogger(
                "thelook_ecommerce_analysis.pipelines.data_processing.nodes"
            ),
            "warning",
        )

        # 1 item válido, 1 item órfão (DC 999)
        ii_df = pd.DataFrame(
            {
                "id": [1, 2],
                "product_id": [1, 1],
                "created_at": pd.to_datetime(["2023-01-01", "2023-01-02"], utc=True),
                "sold_at": [None, None],
                "cost": [10.0, 10.0],
                "product_category": ["A", "A"],
                "product_name": ["A", "A"],
                "product_brand": ["A", "A"],
                "product_retail_price": [20.0, 20.0],
                "product_department": ["A", "A"],
                "product_sku": ["A", "A"],
                "product_distribution_center_id": [1, 999],
            }
        )
        dc_df = pd.DataFrame({"id": [1]})

        ii_table = ibis.memtable(ii_df)
        dc_table = ibis.memtable(dc_df)

        # Mockamos o target para forçar a Exceção do Watermark (Carga Total)
        target_mock = mocker.Mock()
        type(target_mock).created_at = mocker.PropertyMock(
            side_effect=Exception("Table not found")
        )

        res = extract_inventory_items(
            ii_table,
            target_mock,
            dc_table,
            schema_rules=inventory_items_schema,
            columns=list(ii_df.columns),
        )

        # Asserts
        assert res.count().to_pandas() == 1, (
            "Deveria retornar um DataFrame com 1 registro"
        )

        # Verifica se os dois warnings críticos foram disparados (Carga total e Órfãos)
        log_msgs = [call.args[0] for call in spy_logger.call_args_list]
        assert any("Carga total" in msg for msg in log_msgs), (
            "Mensagem de log deveria conter 'Carga total'"
        )
        assert any("INTEGRIDADE REFERENCIAL" in msg for msg in log_msgs), (
            "Mensagem de log deveria ter 'INTEGRIDADE REFERENCIAL'"
        )

    def test_extract_inventory_items_db_exception(self, mocker: MockerFixture) -> None:
        """Testa a falha crítica de banco de dados ao ler distribution_centers dentro de inventory."""

        # Correção: O DataFrame precisa de todas as colunas para passar limpo
        # pelo `transform_inventory_items` antes de chegar no bloco de exceção do DB.
        ii_df = pd.DataFrame(
            {
                "id": [1],
                "product_id": [1],
                "created_at": pd.to_datetime(["2023-01-05"], utc=True),
                "sold_at": [None],
                "cost": [10.0],
                "product_category": ["A"],
                "product_name": ["Prod A"],
                "product_brand": ["Brand A"],
                "product_retail_price": [20.0],
                "product_department": ["Dept A"],
                "product_sku": ["SKU123"],
                "product_distribution_center_id": [1],
            }
        )
        target_df = pd.DataFrame(
            {"created_at": pd.to_datetime(["2023-01-01"], utc=True)}
        )

        # Mock do banco de dados das FKs (Distribution Centers)
        dc_mock = mocker.Mock()
        dc_mock.select.side_effect = Exception("DC DB Failed")

        # Agora o erro levantado será estritamente o do banco de dados, batendo com o Regex
        with pytest.raises(Exception, match="DC DB Failed"):
            extract_inventory_items(
                ibis.memtable(ii_df),
                ibis.memtable(target_df),
                dc_mock,
                inventory_items_schema,
                list(ii_df.columns),
            )

    def test_extract_orders_fk_drop_and_exception(self, mocker: MockerFixture) -> None:
        """Cobre o log de 'dropped > 0' e o except da leitura de users na extração de Orders."""
        spy_logger = mocker.spy(
            logging.getLogger(
                "thelook_ecommerce_analysis.pipelines.data_processing.nodes"
            ),
            "warning",
        )

        orders_df = pd.DataFrame(
            {
                "order_id": [1, 2],
                "user_id": [1, 999],
                "status": ["Processing", "Processing"],
                "created_at": [
                    pd.to_datetime("2023-01-05", utc=True),
                    pd.to_datetime("2023-01-05", utc=True),
                ],
                "shipped_at": [None, None],
                "delivered_at": [None, None],
                "returned_at": [None, None],
                "num_of_item": [1, 2],
            }
        )
        users_df = pd.DataFrame({"id": [1]})

        mock_datetime = mocker.patch(
            "thelook_ecommerce_analysis.pipelines.data_processing.nodes.datetime_"
        )
        mock_datetime.now.return_value = pd.Timestamp("2023-01-06", tz="UTC")

        # 1. Testa Caminho Feliz com Drop de FK (Gera warning)
        res = extract_orders(
            ibis.memtable(orders_df),
            ibis.memtable(users_df),
            10,
            orders_schema,
            list(orders_df.columns),
        )

        # Validação do processamento lógico
        assert res.count().to_pandas() == 1

        # Validação da Observabilidade (Logging)
        log_msgs = [call.args[0] for call in spy_logger.call_args_list]
        assert any("Orders INTEGRIDADE: 1 itens removidos" in msg for msg in log_msgs)

        # 2. Testa Exceção de Banco de Dados
        users_mock = mocker.Mock()
        users_mock.select.side_effect = Exception("User Table Offline")
        with pytest.raises(
            ValueError, match="Erro ao carregar users IDs: User Table Offline"
        ):
            extract_orders(
                ibis.memtable(orders_df), users_mock, 10, {}, list(orders_df.columns)
            )

    def test_extract_order_items_exceptions_and_drops(
        self, mocker: MockerFixture
    ) -> None:
        """Testa blocos de exceção e aviso de queda de itens órfãos na principal tabela fato."""
        spy_logger = mocker.spy(
            logging.getLogger(
                "thelook_ecommerce_analysis.pipelines.data_processing.nodes"
            ),
            "warning",
        )

        # Item 1 (Válido), Item 2 (Order 999 - Inválido)
        items_df = pd.DataFrame(
            {
                "id": [1, 2],
                "order_id": [1, 999],
                "user_id": [1, 1],
                "product_id": [1, 1],
                "inventory_item_id": [1, 1],
                "status": ["Processing", "Processing"],
                "created_at": pd.to_datetime(["2023-01-05", "2023-01-05"], utc=True),
                "shipped_at": pd.to_datetime([None, None]),
                "delivered_at": pd.to_datetime([None, None]),
                "returned_at": pd.to_datetime([None, None]),
                "sale_price": [10.0, 10.0],
            }
        )

        mock_datetime = mocker.patch(
            "thelook_ecommerce_analysis.pipelines.data_processing.nodes.datetime_"
        )
        mock_datetime.now.return_value = pd.Timestamp("2023-01-06", tz="UTC")

        # 1. Caminho Feliz com descarte
        res = extract_order_items(
            ibis.memtable(items_df),
            ibis.memtable(pd.DataFrame({"order_id": [1]})),
            ibis.memtable(pd.DataFrame({"id": [1]})),  # users
            ibis.memtable(pd.DataFrame({"id": [1]})),  # products
            ibis.memtable(pd.DataFrame({"id": [1]})),  # inventory
            10,
            order_items_schema,
            list(items_df.columns),
        )
        assert res.count().to_pandas() == 1, (
            "Deveria retornar um DataFrame com 1 registro"
        )
        log_msgs = [call.args[0] for call in spy_logger.call_args_list]
        assert any(
            "Orders INTEGRIDADE: 1 itens removidos" in msg for msg in log_msgs
        ), "Mensagem de log deve conter 'Orders INTEGRIDADE: 1 itens removidos'"

        # 2. Exceção de Banco de Dados
        orders_mock = mocker.Mock()
        orders_mock.select.side_effect = Exception("Orders DB Connection Error")

        with pytest.raises(ValueError, match="Erro ao carregar FK IDs"):
            extract_order_items(
                ibis.memtable(items_df),
                orders_mock,
                ibis.memtable(pd.DataFrame({"id": [1]})),
                ibis.memtable(pd.DataFrame({"id": [1]})),
                ibis.memtable(pd.DataFrame({"id": [1]})),
                10,
                order_items_schema,
                list(items_df.columns),
            )

    def test_extract_events_happy_path(self) -> None:
        """Testa a extração e validação do schema básico da tabela events."""

        df = pd.DataFrame(
            {
                "id": [1],
                "user_id": [10],
                "sequence_number": [1],
                "session_id": ["abc-123"],
                "created_at": pd.to_datetime(["2023-01-01"], utc=True),
                "city": ["São Paulo"],
                "state": ["SP"],
                "browser": ["Chrome"],
                "traffic_source": ["Organic"],
                "event_type": ["product"],
                "extracted_product_id": [100],
                "extracted_page_type": ["product_page"],
            }
        )
        table = ibis.memtable(df)
        cols = list(df.columns)

        res = extract_events(table, schema_rules=events_schema, columns=cols)

        assert res.count().to_pandas() == 1, (
            "Deveria retornar um DataFrame com 1 registro"
        )
        assert "visitor_type" in res.columns, (
            "Deveria conter a coluna materializada 'visitor_type'"
        )
