import logging
import time
from pathlib import Path
from typing import Any

import psutil
from kedro.config import OmegaConfigLoader
from kedro.framework.hooks import hook_impl
from kedro.io import DataCatalog
from kedro.pipeline import Pipeline
from kedro.pipeline.node import Node
from sqlalchemy import Engine, create_engine, text


class ResourceMonitoringHook:
    """
    Hook completo para monitoramento do Ciclo de Vida e Recursos.

    Funcionalidades:
        1. Logs de início/fim de Pipeline.
        2. Logs de sucesso/erro global.
        3. Monitoramento de tempo e memória (RAM) por nó individual.
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._pipeline_start_time = 0.0
        self._memory_threshold = 1000  # Caso não esteja especificado no parameters.yml

    @property
    def _current_memory_usage(self) -> float:
        """Retorna o uso de memória do processo atual em MB."""
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024

    # ----------------------------------------------------------------
    # 1. Monitoramento Global do Pipeline (Start/Finish/Error)
    # ----------------------------------------------------------------
    @hook_impl
    def before_pipeline_run(
        self, run_params: dict[str, Any], pipeline: Pipeline, catalog: DataCatalog
    ):
        """Executando uma vez no início do comando `kedro run`."""
        self._pipeline_start_time = time.time()

        try:
            # Tenta carregar parameters.yml
            params = catalog.load("parameters")

            # Busca o valor de memória
            monitoring_conf = params.get("monitoring", {})
            self._memory_threshold = monitoring_conf.get(
                "memory_alert_threshold_mb", self._memory_threshold
            )

            self._logger.info(
                f"Configuração de Monitoramento carregada. Alerta definido em: {self._memory_threshold}MB."
            )

        except Exception as e:
            self._logger.warning(
                f"Não foi possível ler parâmetros de monitoramento. Usando padrão ({self._memory_threshold}MB). Erro: {e}."
            )

        self._logger.info("=" * 60)
        self._logger.info("INICIANDO EXECUÇÃO KEDRO")
        self._logger.info("=" * 60)

    @hook_impl
    def after_pipeline_run(
        self, run_params: dict[str, Any], pipeline: Pipeline, catalog: DataCatalog
    ):
        """Executando apenas se o pipeline inteiro finalizar com sucesso."""
        duration = time.time() - self._pipeline_start_time

        self._logger.info("=" * 60)
        self._logger.info("SUCESSO! Pipeline finalizado.")
        self._logger.info(f"Tempo de Execução: {duration:.2f}s")
        self._logger.info("=" * 60)

    @hook_impl
    def on_pipeline_error(
        self,
        error: Exception,
        run_params: dict[str, Any],
        pipeline: Pipeline,
        catalog: DataCatalog,
    ):
        """Executando se o pipeline falhar."""
        duration = time.time() - self._pipeline_start_time

        self._logger.error("=" * 60)
        self._logger.error("FALHA CRÍTICA NO PIPELINE")
        self._logger.error(f"Tempo até a falha: {duration:.2f}s")
        self._logger.error(f"Detalhe do Erro: {error}")
        self._logger.error("=" * 60)

    # ----------------------------------------------------------------
    # 2. Monitoramento Granular de Nós (Memória/Tempo)
    # ----------------------------------------------------------------
    @hook_impl
    def before_node_run(self, node: Node):
        """Executando antes de cada nó."""
        self._node_start_time = time.time()
        self._node_start_mem = self._current_memory_usage
        self._logger.info(f"Executando: {node.namespace} - {node.name}...")

    @hook_impl
    def after_node_run(
        self, node: Node, inputs: dict[str, Any], outputs: dict[str, Any]
    ):
        """Executando após cada nó."""
        end_time = time.time()
        end_mem = self._current_memory_usage
        duration = end_time - self._node_start_time
        mem_delta = end_mem - self._node_start_mem

        # Alerta se o consumo de memória for alto (>1GB)
        mem_flag = ""
        if mem_delta > self._memory_threshold:
            mem_flag = "HIGH MEMORY"

        self._logger.info(
            f"{node.name:<30} | {duration:>6.2f}s | Mem: {end_mem:>7.1f}MB (delta mem: {mem_delta:>+6.1f}MB) {mem_flag}"
        )

    @hook_impl
    def on_node_error(self, node: Node, error: Exception):
        """Executando se um nó específico falhar."""
        self._logger.error(f"Erro no nó '{node.name}': {str(error)}")


class CreateIndexesHook:
    """Cria as tabelas do schema raw_data antes da execução do pipeline e cria os índices após a ingestão dos dados."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _get_engine(self, run_params: dict) -> Engine:
        """Cria engine respeitando o ambiente (local, prod, etc)."""
        env = run_params.get("env", "local")
        loader = OmegaConfigLoader(conf_source="conf", env=env)
        creds = loader["credentials"]["postgres"]
        return create_engine(creds["con"])

    def _execute_sql_files(self, engine: Engine, files_dict: dict):
        """Executa os scripts SQL."""
        with engine.connect() as conn:
            for name, relative_path in files_dict.items():
                sql_path = Path(relative_path)
                if sql_path.exists():
                    self.logger.info(f"Executando SQL: {name}")
                    conn.execute(text(sql_path.read_text(encoding="utf-8")))
                    conn.commit()
                else:
                    self.logger.warning(f"Arquivo SQL não encontrado: {sql_path}")

    @hook_impl
    def before_pipeline_run(
        self, run_params: dict[str, Any], pipeline: Pipeline, catalog: DataCatalog
    ):
        """Cria as tabelas do schema raw_data antes da execução do pipeline."""
        # Carrega parâmetros diretamente do catálogo (já carregado pelo Kedro)
        # Isso é mais seguro que instanciar OmegaConfigLoader para 'parameters'
        params = catalog.load("parameters")

        if "sql" in params:
            self.logger.info("Verificando tabelas iniciais...")
            engine = self._get_engine(run_params)

            self._execute_sql_files(engine, params["sql"])
            return

    @hook_impl
    def after_pipeline_run(
        self, run_params: dict[str, Any], pipeline: Pipeline, catalog: DataCatalog
    ):
        """Cria os índices após a ingestão dos dados."""
        params = catalog.load("parameters")

        if "indexes" in params:
            self.logger.info("Criando índices finais...")
            engine = self._get_engine(run_params)
            self._execute_sql_files(engine, params["indexes"])
