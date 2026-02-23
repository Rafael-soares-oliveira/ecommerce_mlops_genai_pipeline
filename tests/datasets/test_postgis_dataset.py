from typing import Any

import pytest
from kedro.io.core import DatasetError
from pytest_mock import MockerFixture
from sqlalchemy.engine import Connection, Engine

from thelook_ecommerce_analysis.datasets.sql_executable_dataset import (
    PostGISScriptDataset,
)


@pytest.fixture
def mock_credentials() -> dict[str, str]:
    return {"con": "postgresql://user:pass@localhost:5432/db"}


@pytest.fixture
def dataset(mock_credentials: dict[str, str]) -> PostGISScriptDataset:
    return PostGISScriptDataset(sql_script="test.sql", credentials=mock_credentials)


class TestPostGISScriptDataset:
    def test_describe(self, dataset: PostGISScriptDataset) -> None:
        assert dataset._describe() == {"sql_path": "test.sql"}

    def test_save_raises_error(self, dataset: PostGISScriptDataset) -> None:
        """Garante que o método save levanta erro com a mensagem correta."""
        # Ajustado para bater com a mensagem real do seu src
        with pytest.raises(DatasetError, match="apenas para execução de scripts"):
            dataset._save(data={})

    def test_load_success(
        self, mocker: MockerFixture, dataset: PostGISScriptDataset
    ) -> None:
        """Testa o fluxo de carga utilizando MockerFixture."""
        # Mock do open (Built-in)
        mocker.patch(
            "builtins.open", mocker.mock_open(read_data="CREATE TABLE t (id INT);")
        )

        # Mock do SQLAlchemy
        mock_engine = mocker.MagicMock(spec=Engine)
        mock_conn = mocker.MagicMock(spec=Connection)

        # O patch retorna o mock que ele substituiu
        mock_create_engine = mocker.patch(
            "thelook_ecommerce_analysis.datasets.sql_executable_dataset.create_engine",
            return_value=mock_engine,
        )
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        params: dict[str, Any] = {"id_val": 10}
        result: bool = dataset._load(params=params)

        # Asserts
        assert result is True
        mock_create_engine.assert_called_once_with(dataset._credentials["con"])
        mock_conn.commit.assert_called_once()

    def test_load_security_failure(
        self, mocker: MockerFixture, dataset: PostGISScriptDataset
    ) -> None:
        """Garante que o load falha e não abre conexão se o SQL for proibido."""
        # Mock do arquivo com comando proibido
        mocker.patch("builtins.open", mocker.mock_open(read_data="DROP TABLE secret;"))

        # Patch correto no caminho do seu projeto
        mock_create_engine = mocker.patch(
            "thelook_ecommerce_analysis.datasets.sql_executable_dataset.create_engine"
        )

        # O erro deve ser disparado aqui
        with pytest.raises(DatasetError, match="Ação negada"):
            dataset._load()

        # Agora o assert_not_called deve passar pois a exceção trava o fluxo antes
        mock_create_engine.assert_not_called()

    @pytest.mark.parametrize(
        "sql", ["CREATE TABLE x (id INT);", "COMMENT ON TABLE x IS 'y';"]
    )
    def test_validate_sql_success(
        self, dataset: PostGISScriptDataset, sql: str
    ) -> None:
        # Não deve levantar exceção
        dataset._validate_sql(sql)

    @pytest.mark.parametrize("sql", ["SELECT * FROM x;", "DROP TABLE x;"])
    def test_validate_sql_denied(self, dataset: PostGISScriptDataset, sql: str) -> None:
        with pytest.raises(DatasetError, match="Ação negada"):
            dataset._validate_sql(sql)
