import ibis
import numpy as np
import pandas as pd
import polars as pl
import pytest
from pytest_mock import MockerFixture

# IMPORTANTE: Ajuste o caminho de importação para o seu projeto!
from thelook_ecommerce_analysis.pipelines.data_embeddings.nodes import (
    execute_sql_query,
    fct_user_logistics,
    generate_embeddings,
    map_hotspots_h3,
    prepare_products_for_embedding,
    prepare_users_for_embedding,
)


class TestEmbeddingsNodes:
    """Suíte de testes para os nós de preparação e geração de Embeddings."""

    def test_execute_sql_query(self, mocker: MockerFixture) -> None:
        """Testa a função de passagem de execução de SQL direto."""
        mock_table = mocker.MagicMock()
        mock_table.get_name.return_value = "my_table"

        assert execute_sql_query(mock_table, True) is True
        assert execute_sql_query(mock_table, False) is False

    def test_fct_user_logistics_and_map_hotspots(self, mocker: MockerFixture) -> None:
        """Testa as funções de passagem (dummy) que retornam o trigger."""
        mock_table = mocker.MagicMock()

        # Como são funções pass-through, apenas validamos se repassam o booleano
        assert (
            fct_user_logistics(
                mock_table, mock_table, mock_table, mock_table, mock_table, True
            )
            is True
        )
        assert map_hotspots_h3(mock_table, False) is False

    def test_prepare_products_for_embedding(self) -> None:
        """Garante a formatação correta do texto do chunk e tratamento de nulos em produtos."""
        df = pd.DataFrame(
            {
                "id": [1, 2],
                "name": ["Camisa", None],
                "brand": ["Nike", None],
                "category": ["Roupas", None],
                "department": ["Masculino", None],
                "retail_price": [59.90, 100.00],
            }
        )
        table = ibis.memtable(df)

        res_table = prepare_products_for_embedding(table, trigger=True)
        res_df = res_table.to_pandas()

        # Valida o Produto 1 (Caminho Feliz)
        expected_text_1 = "Produto: Camisa, Marca: Nike, Categoria: Roupas, Depto: Masculino, Preço: $59.9"
        assert res_df["chunk_text"].iloc[0] == expected_text_1
        assert res_df["source_id"].dtype == "int64"

        # Valida o Produto 2 (Caminho com Nulos preenchidos com Unknown)
        expected_text_2 = "Produto: Unknown, Marca: Unknown, Categoria: Unknown, Depto: Unknown, Preço: $100.0"
        assert res_df["chunk_text"].iloc[1] == expected_text_2

    def test_prepare_users_for_embedding(self) -> None:
        """Valida agregação de gasto médio (Join) e formatação de texto de usuários."""
        users_df = pd.DataFrame(
            {
                "id": [1, 2],
                "city": ["São Paulo", None],
                "state": ["SP", None],
                "country": ["Brasil", None],
                "latitude": [10.0, 20.0],
                "longitude": [-10.0, -20.0],
            }
        )
        # Usuário 1 comprou 2 itens (Gasto médio = 15.0). Usuário 2 não comprou nada.
        order_items_df = pd.DataFrame(
            {
                "user_id": [1, 1],
                "sale_price": [10.0, 20.0],
            }
        )

        users_table = ibis.memtable(users_df)
        items_table = ibis.memtable(order_items_df)

        res_table = prepare_users_for_embedding(users_table, items_table, trigger=True)
        res_df = res_table.to_pandas().sort_values("user_id").reset_index(drop=True)

        # Valida Usuário 1 (Com compras e cidade)
        assert (
            "Cliente localizado em São Paulo, SP, Brasil. Gasto médio: $15.0"
            in res_df["chunk_text"].iloc[0]
        )
        assert res_df["avg_spend"].iloc[0] == 15.0

        # Valida Usuário 2 (Sem compras/nulo e sem cidade)
        assert (
            "Cliente localizado em Unknown, Unknown, Unknown. Gasto médio: $0.0"
            in res_df["chunk_text"].iloc[1]
        )
        assert res_df["avg_spend"].iloc[1] == 0.0

    def test_generate_embeddings_success(self, mocker: MockerFixture) -> None:
        """Testa geração de embeddings vetorizados mockando o modelo SentenceTransformer."""
        # Criamos um DataFrame Polars com um texto válido e uma coluna puramente nula
        pl_df = pl.DataFrame(
            {
                "chunk_text": ["Texto 1", "Texto 2"],
                "outra_coluna": [1, 2],
                "coluna_nula": pl.Series([None, None], dtype=pl.Null),
            }
        )

        # Mock do ibis.Table e a sua conversão para Arrow
        mock_table = mocker.MagicMock()
        mock_table.to_pyarrow.return_value = pl_df.to_arrow()

        # Mock do Modelo de Embedding
        mock_model = mocker.MagicMock()

        # Simulamos a saída de um modelo do HuggingFace: Uma matriz Numpy Nx384
        # N=2 porque enviamos duas linhas no dataframe
        fake_embeddings = np.zeros((2, 384), dtype=np.float32)
        mock_model.encode.return_value = fake_embeddings

        # Act
        result_df = generate_embeddings(mock_table, mock_model, batch_size=256)

        # Assert
        assert isinstance(result_df, pl.DataFrame), "Deve retornar um Polars DataFrame"

        # Verifica se o método de encode foi chamado com a lista correta extraída do Polars
        mock_model.encode.assert_called_once_with(
            ["Texto 1", "Texto 2"],
            batch_size=256,
            show_progress_bar=True,
            normalize_embeddings=True,
        )

        # Valida o Zero-Copy insertion (a coluna embedding)
        assert "embedding" in result_df.columns
        assert result_df["embedding"].dtype == pl.Array(pl.Float32, 384), (
            "A coluna embedding precisa ter o tipo fixo Array(Float32, 384)"
        )

        # Valida a lógica de tratamento de Nulls do Polars (linha 47 do seu node)
        assert result_df["coluna_nula"].dtype == pl.String, (
            "Colunas que eram pl.Null devem ser castadas para pl.String"
        )

    def test_generate_embeddings_type_error(self, mocker: MockerFixture) -> None:
        """Garante que falha no from_arrow levanta TypeError explícito."""
        mock_table = mocker.MagicMock()
        mock_model = mocker.MagicMock()

        # Mockamos diretamente a função polars.from_arrow para forçar o retorno de uma Series
        # (Isso simula o caso onde o pyarrow retorna um Array unidimensional em vez de Table)
        mocker.patch("polars.from_arrow", return_value=pl.Series("erro", [1, 2, 3]))

        with pytest.raises(TypeError, match="A conversão resultou em uma Series"):
            generate_embeddings(mock_table, mock_model)
