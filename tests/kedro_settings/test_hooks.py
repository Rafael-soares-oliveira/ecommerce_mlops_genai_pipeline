from pathlib import Path
from unittest.mock import MagicMock, PropertyMock

import pytest
from kedro.io import DataCatalog
from kedro.pipeline import Pipeline, node
from kedro.pipeline.node import Node
from pytest_mock import MockerFixture
from sqlalchemy import Engine

from thelook_ecommerce_analysis.hooks import CreateIndexesHook, ResourceMonitoringHook

# Importe suas classes aqui
# from seu_projeto.hooks import ResourceMonitoringHook, CreateIndexesHook


class TestResourceMonitoringHook:
    @pytest.fixture
    def hook(self) -> ResourceMonitoringHook:
        return ResourceMonitoringHook()

    @pytest.fixture
    def mock_catalog(self) -> MagicMock:
        catalog = MagicMock(spec=DataCatalog)
        # Simula o carregamento de parâmetros
        catalog.load.return_value = {"monitoring": {"memory_alert_threshold_mb": 500}}
        return catalog

    @pytest.fixture
    def mock_node(self) -> Node:
        return node(
            lambda x: x, "input", "output", name="test_node", namespace="test_ns"
        )

    def test_before_pipeline_run_success(
        self, hook: ResourceMonitoringHook, mock_catalog: MagicMock
    ):
        run_params = {"env": "local"}
        pipeline = MagicMock(spec=Pipeline)

        hook.before_pipeline_run(run_params, pipeline, mock_catalog)

        assert hook._memory_threshold == 500
        assert hook._pipeline_start_time > 0

    def test_before_pipeline_run_error_fallback(self, hook: ResourceMonitoringHook):
        # Simula catálogo que falha ao carregar
        catalog = MagicMock(spec=DataCatalog)
        catalog.load.side_effect = Exception("Load error")

        hook.before_pipeline_run({}, MagicMock(), catalog)
        # Deve manter o padrão definido no __init__ (1000)
        assert hook._memory_threshold == 1000

    def test_after_pipeline_run(self, hook: ResourceMonitoringHook):
        hook._pipeline_start_time = 100.0  # mock start time
        hook.after_pipeline_run({}, MagicMock(), MagicMock())
        # Apenas verifica se não quebra ao logar

    def test_on_pipeline_error(self, hook: ResourceMonitoringHook):
        hook.on_pipeline_error(Exception("Fail"), {}, MagicMock(), MagicMock())
        # Verifica fallback de log

    def test_node_lifecycle(
        self, hook: ResourceMonitoringHook, mock_node: Node, mocker: MockerFixture
    ):
        """Testa o ciclo de vida do nó e o alerta de memória alta."""
        # 1. Setup do threshold e valores iniciais
        hook._memory_threshold = 50  # MB

        # 2. Mockando a @property _current_memory_usage na CLASSE
        # Usamos dois valores diferentes para simular o consumo subindo (100MB -> 200MB)
        mock_mem = mocker.patch.object(
            ResourceMonitoringHook, "_current_memory_usage", new_callable=PropertyMock
        )
        mock_mem.side_effect = [
            100.0,
            200.0,
        ]  # Primeiro valor para o 'before', segundo para o 'after'

        # 3. Execução
        hook.before_node_run(mock_node)

        # Verificamos se o tempo e memória inicial foram capturados
        assert hook._node_start_mem == 100.0
        assert hook._node_start_time > 0

        # 4. Finalização do nó
        # Aqui o delta será 100.0 (200 - 100), que é > threshold (50)
        hook.after_node_run(mock_node, inputs={}, outputs={})

        # O teste passa se não houver TypeError na comparação 'if mem_delta > self._memory_threshold'

    def test_on_node_error(self, hook: ResourceMonitoringHook, mock_node: Node):
        hook.on_node_error(mock_node, Exception("Node crash"))


class TestCreateIndexesHook:
    @pytest.fixture
    def hook(self) -> CreateIndexesHook:
        return CreateIndexesHook()

    @pytest.fixture
    def mock_engine(self) -> MagicMock:
        return MagicMock(spec=Engine)

    def test_get_engine(self, hook: CreateIndexesHook, mocker: MockerFixture):
        # Mock do OmegaConfigLoader para não ler arquivos reais
        mock_loader = mocker.patch("thelook_ecommerce_analysis.hooks.OmegaConfigLoader")
        mock_loader.return_value = {
            "credentials": {"postgres": {"con": "postgresql://..."}}
        }

        mock_create = mocker.patch("thelook_ecommerce_analysis.hooks.create_engine")

        hook._get_engine({"env": "local"})
        mock_create.assert_called_once()

    def test_execute_sql_files_success(
        self, hook: CreateIndexesHook, mock_engine: MagicMock, tmp_path: Path
    ):
        # Criar arquivo SQL temporário
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1", encoding="utf-8")

        files_dict = {"test_query": str(sql_file)}

        mock_conn = mock_engine.connect.return_value.__enter__.return_value

        hook._execute_sql_files(mock_engine, files_dict)

        mock_conn.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_execute_sql_files_not_found(
        self, hook: CreateIndexesHook, mock_engine: MagicMock
    ):
        files_dict = {"missing": "non_existent.sql"}
        hook._execute_sql_files(mock_engine, files_dict)
        # Não deve chamar execute
        mock_engine.connect.return_value.__enter__.return_value.execute.assert_not_called()

    def test_hooks_run_conditions(self, hook: CreateIndexesHook, mocker: MockerFixture):
        # Mock catalog
        catalog = MagicMock(spec=DataCatalog)
        catalog.load.return_value = {
            "sql": {"init": "path/to.sql"},
            "indexes": {"idx": "path/idx.sql"},
        }

        # Mock engine e execute_sql para não tocar no banco
        mocker.patch.object(hook, "_get_engine")
        mocker.patch.object(hook, "_execute_sql_files")

        # Test before_pipeline
        hook.before_pipeline_run({}, MagicMock(), catalog)

        # Test after_pipeline
        hook.after_pipeline_run({}, MagicMock(), catalog)
