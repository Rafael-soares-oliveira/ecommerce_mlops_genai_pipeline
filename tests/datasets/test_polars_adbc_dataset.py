import polars as pl
import pytest
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis.datasets.polars_adbc_dataset import (
    PolarsVectorADBCDataset,
)


@pytest.fixture
def mock_credentials() -> dict[str, str]:
    """Fornece as credenciais de teste mockadas."""
    return {"con": "postgresql://user:pass@localhost:5432/db"}


@pytest.fixture
def dataset(mock_credentials: dict[str, str]) -> PolarsVectorADBCDataset:
    """Instancia o dataset com os parâmetros base configurados."""
    return PolarsVectorADBCDataset(
        credentials=mock_credentials,
        table_name="test_table",
        schema="custom_schema",
        has_geo=True,
    )


class TestPolarsVectorADBCDataset:
    def test_describe(self, dataset: PolarsVectorADBCDataset) -> None:
        """Testa o método _describe para validar o retorno dos metadados."""
        desc = dataset._describe()
        assert desc["table"] == "test_table"
        assert desc["has_geo"] is True
        assert desc["engine"] == "adbc"

    def test_ensure_dataframe_with_lazy(self, dataset: PolarsVectorADBCDataset) -> None:
        """Testa a conversão de um LazyFrame para DataFrame materializado."""
        df = pl.DataFrame({"a": [1]})
        lazy_df = df.lazy()
        # Chama o método interno para garantir a cobertura
        result = dataset._ensure_dataframe(lazy_df)
        assert isinstance(result, pl.DataFrame)

    def test_save_success_with_casts(
        self, mocker: MockerFixture, dataset: PolarsVectorADBCDataset
    ) -> None:
        """Testa o save e os condicionais de cast (embedding/geo)."""
        # DataFrame com colunas que disparam os IFs de cast
        df = pl.DataFrame(
            {
                "id": [1],
                "embedding": ["[0.1, 0.2]"],
                "latitude": [0.0],
                "longitude": [0.0],
            }
        )

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()

        # Configuração vital para o context manager 'with pg_adbc.connect(...) as conn'
        mocker.patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn)
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mocker.patch.object(pl.DataFrame, "write_database")

        dataset._save(df)

        # Verifica se os comandos SQL de cast foram gerados
        insert_sql = mock_cursor.execute.call_args_list[0].args[0]

        assert "::text, '{', '['), '}', ']')::vector" in insert_sql, (
            "::text, '{', '['), '}', ']')::vector deveria ter sido executado."
        )
        assert "ST_SetSRID" in insert_sql, "ST_SetSRID deveria ter sido executado."
        assert mock_cursor.execute.call_count == 2, (
            "Deveria ter 2 execuções (Insert & Drop)"
        )

    def test_save_cleanup_on_failure(
        self, mocker: MockerFixture, dataset: PolarsVectorADBCDataset
    ) -> None:
        """Garante que o DROP ocorre mesmo com erro, cobrindo o bloco finally."""
        df = pl.DataFrame({"id": [1]})

        mock_conn = mocker.MagicMock()
        mock_cursor = mocker.MagicMock()

        mocker.patch("adbc_driver_postgresql.dbapi.connect", return_value=mock_conn)
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mocker.patch.object(pl.DataFrame, "write_database")

        # Primeiro execute falha, o segundo (no finally) deve ser chamado
        mock_cursor.execute.side_effect = [RuntimeError("DB Fail"), None]

        with pytest.raises(RuntimeError, match="DB Fail"):
            dataset._save(df)

        # Verifica se o DROP TABLE foi chamado na segunda execução do cursor
        assert mock_cursor.execute.call_count == 2
        assert "DROP TABLE IF EXISTS" in mock_cursor.execute.call_args_list[1][0][0]

    def test_load(
        self, mocker: MockerFixture, dataset: PolarsVectorADBCDataset
    ) -> None:
        """Testa o load garantindo que a query bate com o f-string original."""
        mocker.patch("adbc_driver_postgresql.dbapi.connect")
        mock_read = mocker.patch("polars.read_database", return_value=pl.DataFrame())

        dataset._load()

        expected_query = "SELECT * FROM custom_schema.test_table"
        assert mock_read.call_args.kwargs["query"] == expected_query
