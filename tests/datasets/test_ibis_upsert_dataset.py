import re
from typing import Any
from unittest.mock import MagicMock, PropertyMock

import pytest
from kedro.io import DatasetError
from pytest_mock import MockerFixture
from sqlalchemy.testing.engines import mock_engine

from thelook_ecommerce_analysis.datasets.ibis_upsert_dataset import IbisUpsertDataset


class TestIbisUpsertDataset:
    """Suíte de testes para a classe IbisUpsertDataset."""

    @pytest.fixture
    def base_kwargs(self) -> dict[str, Any]:
        """Fornece os argumentos básicos para instanciar a classe sem erros."""
        # "connection" removido, será mockado via PropertyMock. Atributo "connection" é definido com o decorador @property, portanto não possui um "setter" e não pode ser rescrito com MagicMock().
        return {
            "table_name": "my_table",
            "connection": {"backend": "postgres"},
            "save_args": {"mode": "upsert"},  # Default para os testes de upsert
        }

    @pytest.fixture
    def dataset(
        self, base_kwargs: dict[str, Any], mocker: MockerFixture
    ) -> IbisUpsertDataset:
        """Cria uma instância padrão do dataset com o super().__init__ mockado."""
        mock_connection = MagicMock()

        # Garantir que não retorne True para qualquer hasattr. Cria a necessidade de recriar a conexão
        if hasattr(mock_connection, "engine"):
            del mock_connection.engine

        # Uso do PropertyMock para simular o @property 'connection' da classe
        mocker.patch.object(
            target=IbisUpsertDataset,
            attribute="connection",
            new_callable=PropertyMock,
            return_value=mock_connection,
        )

        ds = IbisUpsertDataset(**base_kwargs)
        ds._connection_config = {
            "backend": "postgres",
            "drivername": "postgresql+psycopg",
            "host": "localhost",
            "database": "testdb",
            "user": "testuser",
            "password": "password",
            "schema": "public",
        }

        return ds

    @pytest.fixture
    def mock_arrow_table(self) -> MagicMock:
        """Simula uma tabela do PyArrow retornada pelo Ibis."""
        arrow_mock = MagicMock()
        arrow_mock.num_rows = 10
        arrow_mock.column_names = ["id", "nome", "idade"]
        arrow_mock.to_batches.return_value = [MagicMock()]
        return arrow_mock

    @pytest.fixture
    def mock_ibis_table(self, mock_arrow_table: MagicMock) -> MagicMock:
        """Simula a tabela ibis.expr.types do Ibis que entra no método save()."""
        ibis_mock = MagicMock()
        ibis_mock.to_pyarrow.return_value = mock_arrow_table
        return ibis_mock

    # 1. Testes de Inicialização e Helpers
    def test_init_upsert_mode(
        self, mocker: MockerFixture, base_kwargs: dict[str, Any]
    ) -> None:
        """Verifica se o modo 'upsert' é convertido para 'append' e a flag é ativada."""
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.TableDataset.__init__",
            return_value=None,
        )
        kwargs = {**base_kwargs, "save_args": {"mode": "upsert"}}

        ds = IbisUpsertDataset(**kwargs)

        assert ds._is_upsert is True, "Deveria ser 'True'."

    def test_ensure_list(self, dataset: IbisUpsertDataset) -> None:
        """Testa o helper que garante o formato de lista."""
        assert dataset._ensure_list(None) == [], "Deveria ser uma lista vazia."
        assert dataset._ensure_list("col1") == ["col1"], (
            "Deveria retornar uma lista com registro único 'col1'."
        )
        assert dataset._ensure_list(["col1", "col2"]) == ["col1", "col2"], (
            "Deveria retornar uma lista com 2 registros 'col1' e 'col2'."
        )

    # 2. Testes de Engine do SQLAlchemy
    def test_get_sqlalchemy_engine_existing(self, dataset: IbisUpsertDataset) -> None:
        """Testa se retorna a engine já existente na conexão."""
        dataset.connection.engine = mock_engine
        assert dataset._get_sqlalchemy_engine() == mock_engine, (
            "Engine deveria retornar a conexão já existente."
        )

    def test_get_sqlalchemy_engine_configuration(
        self, dataset: IbisUpsertDataset, mocker: MockerFixture
    ) -> None:
        """Testa os argumentos passados para a criação da URL do SQLAlchemy."""
        mock_create_engine = mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.create_engine"
        )

        dataset._get_sqlalchemy_engine()

        # Capturar a URL passada para o create_engine
        args, kwargs = mock_create_engine.call_args
        url = args[0]

        assert url.drivername == "postgresql+psycopg"
        assert url.host == "localhost"
        assert url.database == "testdb"
        assert url.username == "testuser"
        assert url.password == "password"  # noqa: S105 -> ruff considera como hardcode

    # 3. Testes do Método Save
    def test_save_not_upsert(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Se não for upsert, deve chamar o save() da classe pai."""
        dataset._is_upsert = False

        mock_super_save = mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.TableDataset.save"
        )

        dataset.save(mock_ibis_table)

        mock_super_save.assert_called_once_with(mock_ibis_table)

    def test_save_empty_table(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Testa se retorna sem fazer nada quando a tabela estiver vazia."""
        dataset._is_upsert = True

        mock_ibis_table.to_pyarrow.return_value.num_rows = 0

        spy_engine = mocker.spy(dataset, "_get_sqlalchemy_engine")

        dataset.save(mock_ibis_table)

        assert spy_engine.call_count == 0, "Função não deveria ter sido chamada."

    def test_save_missing_columns(
        self, dataset: IbisUpsertDataset, mock_ibis_table: MagicMock
    ) -> None:
        """Testa se levanta erro quando não configuramos colunas que não existem no dataframe."""
        dataset._is_upsert = True
        dataset._save_args = {"columns": ["coluna_inexistente"]}

        with pytest.raises(DatasetError, match="Colunas configuradas ausentes"):
            dataset.save(mock_ibis_table)

    def test_save_upsert_raw_conn_none(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Testa a exceção quando o driver_connection falha (retorna None)."""
        dataset._is_upsert = True

        mock_engine = MagicMock()
        mock_conn = mock_engine.begin.return_value.__enter__.return_value
        mock_conn.connection.driver_connection = None
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)

        # Precisamos mockar o ArrowToPostgresBinaryEncoder da biblioteca pgpq
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        with pytest.raises(Exception, match="Falha na conexão nativa psycopg."):
            dataset.save(mock_ibis_table)

    def test_save_upsert_calls_correct_sql(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Testa o caminho feliz completo de um Upsert."""
        dataset._is_upsert = True

        mock_engine = MagicMock()
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)

        mock_encoder_class = mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )
        mock_encoder = mock_encoder_class.return_value
        mock_encoder.write_header.return_value = b"header"  # Converte para bytes
        mock_encoder.write_batch.return_value = b"batch"
        mock_encoder.finish.return_value = b"finish"

        dataset.save(mock_ibis_table)

        # O último execute deve conter o INSERT INTO ... ON CONFLICT
        args, _ = mock_engine.begin().__enter__().execute.call_args
        sql_query = str(args[0])

        assert "ON CONFLICT" in sql_query, "'ON CONFLICT' deveria ter sido executado."
        assert "DO UPDATE SET" in sql_query, (
            "'DO UPDATE SET' deveria ter sido executado."
        )
        assert "tmp_my_table" in sql_query, (
            "Tabela temporária 'tmp_my_table' deveria ter sido criada."
        )

    def test_save_upsert_do_nothing(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """Testa o cenário onde todas as colunas são índices ou excluídas, gerando DO NOTHING."""
        dataset._is_upsert = True

        # 1. Garantimos que TODAS as colunas do mock_ibis_table estejam protegidas
        # As colunas no seu mock são ["id", "nome", "idade"]
        dataset._save_args = {
            "index_elements": ["id"],
            "exclude_from_update": ["nome", "idade"],
        }

        # 2. Mock do Engine e do fluxo transacional (Context Manager)
        mock_engine = MagicMock()
        # Simula: with engine.begin() as conn:
        mock_conn = mock_engine.begin.return_value.__enter__.return_value
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)

        # 3. Mock da conexão nativa para o COPY
        # Simula: conn.connection.driver_connection
        mock_driver_conn = MagicMock()
        mock_conn.connection.driver_connection = mock_driver_conn

        # 4. Mock do Encoder para evitar erros de importação/inicialização
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        # 5. Execução
        dataset.save(mock_ibis_table)

        # 6. Verificação
        # O UPSERT SQL é a última chamada de execute no mock_conn
        assert mock_conn.execute.called

        # Pegamos o texto do SQL da última chamada
        last_call_args = mock_conn.execute.call_args_list[-1][0]
        sql_executado = str(last_call_args[0])

        assert "DO NOTHING" in sql_executado
        assert "DO UPDATE SET" not in sql_executado

    def test_save_upsert_with_global_config(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ):
        """Testa se o dataset prioriza configurações do global_config."""
        dataset._is_upsert = True
        dataset._table_name = "minha_tabela"

        # Configuração global que deve sobrescrever o comportamento padrão
        dataset._save_args = {
            "global_config": {
                "minha_tabela": {
                    "index_elements": ["uuid"],
                    "exclude_from_update": ["criado_em"],
                }
            }
        }

        mock_engine = MagicMock()
        mock_conn = mock_engine.begin.return_value.__enter__.return_value
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        dataset.save(mock_ibis_table)

        # Verifica se o SQL gerado usou o index_elements do global_config
        last_sql = str(mock_conn.execute.call_args_list[-1][0][0])
        assert 'ON CONFLICT ("uuid")' in last_sql

    def test_save_upsert_binary_copy_execution(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ):
        """Garante que os métodos de escrita binária do psycopg foram chamados."""
        dataset._is_upsert = True
        mock_engine = MagicMock()
        mock_conn = mock_engine.begin.return_value.__enter__.return_value
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)

        # Mock do cursor e do contexto de cópia
        mock_cursor = mock_conn.connection.driver_connection.cursor.return_value.__enter__.return_value
        mock_copy = mock_cursor.copy.return_value.__enter__.return_value

        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        dataset.save(mock_ibis_table)

        # Verifica se houve escrita no stream binário
        assert mock_copy.write.called
        # Verifica se o SQL de COPY foi gerado corretamente para a tabela temporária
        copy_sql = mock_cursor.copy.call_args[0][0]
        assert "COPY tmp_my_table" in copy_sql
        assert "FORMAT BINARY" in copy_sql

    def test_save_upsert_transaction_rollback_on_error(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ):
        """Verifica se uma exceção durante o COPY interrompe o processo."""
        dataset._is_upsert = True
        mock_engine = MagicMock()
        # Força um erro dentro do bloco transacional
        mock_engine.begin.side_effect = Exception("Erro de Banco")
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)

        with pytest.raises(Exception, match="Erro de Banco"):
            dataset.save(mock_ibis_table)

    def test_init_raises_error_on_mode_conflict(self, base_kwargs: dict[str, Any]):
        """Verifica se impede a criação do dataset com parâmetros conflitantes."""
        base_kwargs["save_args"] = {"mode": "upsert", "overwrite": True}

        # Aqui testamos a validação de erro do Kedro que você herdou/manteve
        with pytest.raises(
            ValueError, match="Cannot specify both 'mode' and deprecated 'overwrite'"
        ):
            IbisUpsertDataset(**base_kwargs)

    def test_save_upsert_is_distinct_logic(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ):
        """Verifica se o WHERE do UPSERT contém a lógica de 'IS DISTINCT FROM'."""
        dataset._is_upsert = True
        # Simulamos colunas que devem ser comparadas
        dataset._save_args = {"index_elements": ["id"], "exclude_from_update": []}

        mock_engine = MagicMock()
        mock_conn = mock_engine.begin.return_value.__enter__.return_value
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        dataset.save(mock_ibis_table)

        last_sql = str(mock_conn.execute.call_args_list[-1][0][0])

        # Verifica se a comparação inteligente de colunas existe
        assert 'IS DISTINCT FROM EXCLUDED."nome"' in last_sql
        assert 'IS DISTINCT FROM EXCLUDED."idade"' in last_sql
        assert "WHERE" in last_sql

    def test_save_upsert_column_filtering(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ):
        """Verifica se o dataset filtra as colunas da tabela Arrow antes do COPY."""
        dataset._is_upsert = True
        # Queremos salvar apenas a coluna 'id'
        dataset._save_args = {"columns": ["id"]}

        mock_engine = MagicMock()
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        # Spy no método select da tabela arrow (que é o mock_arrow_table dentro do mock_ibis_table)
        mock_arrow = mock_ibis_table.to_pyarrow.return_value

        dataset.save(mock_ibis_table)

        # Verifica se o select foi chamado com a lista correta
        mock_arrow.select.assert_called_once_with(["id"])

    def test_save_upsert_temporary_table_consistency(
        self,
        dataset: IbisUpsertDataset,
        mock_ibis_table: MagicMock,
        mocker: MockerFixture,
    ):
        """Verifica se a mesma tabela temporária é usada no CREATE, COPY e INSERT."""
        dataset._is_upsert = True
        mock_engine = MagicMock()
        mock_conn = mock_engine.begin.return_value.__enter__.return_value
        mocker.patch.object(dataset, "_get_sqlalchemy_engine", return_value=mock_engine)
        mocker.patch(
            "thelook_ecommerce_analysis.datasets.ibis_upsert_dataset.ArrowToPostgresBinaryEncoder"
        )

        dataset.save(mock_ibis_table)

        # Capturamos todos os comandos executados
        executed_sqls = [str(call[0][0]) for call in mock_conn.execute.call_args_list]

        # Busca o nome da tmp_table no comando CREATE

        match = re.search(r"CREATE TEMP TABLE (tmp_my_table_\w+)", executed_sqls[0])
        assert match, "Não encontrou padrão de tabela temporária no primeiro SQL."

        temp_table_name = match.group(1)

        # Verifica se o UPSERT final (último SQL) usa a MESMA tabela temporária
        assert f"FROM {temp_table_name}" in executed_sqls[-1]
