import logging
import time
from typing import Any

import pyarrow as pa
import sqlglot
from ibis.backends.postgres import Backend as PostgresBackend
from sqlglot import exp

logger = logging.getLogger(__name__)


class QueryExecutionStats:
    """Extrai métricas da execução da query."""

    def __init__(self, query: str):
        self.query = query
        self.start_time = None
        self.end_time = None
        self.rows_returned = 0
        self.error = None

    def start(self) -> None:
        self.start_time = time.time()

    def end(self, rows: int = 0) -> None:
        self.end_time = time.time()
        self.rows_returned = rows

    @property
    def duration_ms(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def __str__(self) -> str:
        status = "✅" if not self.error else "❌"
        return f"{status} Query executada em {self.duration_ms:.2f}ms | Rows: {self.rows_returned}"


def is_read_only_query(sql_query: str) -> bool:  # noqa: PLR0911
    """Validação de segurança baseada em AST (Abstract Syntax Tree) usando sqlglot. Garante que a query é estritamente de leitura, mesmo com CTEs complexas."""
    if not sql_query or not sql_query.strip():
        return False

    try:
        expressions = sqlglot.parse(sql_query, read="postgres")
    except sqlglot.errors.ParseError as e:
        logger.error(f"Erro de sintaxe ao fazer parse do SQL: {e}")
        return False

    # Filtra None gerado por strings vazias ou apenas com comentários
    expressions = [e for e in (expressions or []) if e is not None]

    if not expressions:
        return False

    # Tipos de nós AST que indicam mutação de dados ou alteração de schema
    dangerous_node_names = [
        "Insert",
        "Update",
        "Delete",
        "Drop",
        "Alter",
        "Create",
        "TruncateTable",
        "Commit",
        "Rollback",
    ]

    dangerous_types = tuple(
        getattr(exp, name) for name in dangerous_node_names if hasattr(exp, name)
    )

    for expression in expressions:
        root_class = expression.__class__.__name__

        # 1. A instrução raiz deve ser obrigatoriamente um SELECT, UNION ou 'Command' se começar com EXPLAIN
        is_explain_command = root_class == "Command" and str(
            expression
        ).upper().startswith("EXPLAIN")

        if root_class not in ("Select", "Union", "Explain") and not is_explain_command:
            logger.warning(
                f"Query bloqueada: Instrução principal '{root_class}' não é de leitura."
            )
            return False

        # 2. Deep scan por nós de mutação escondidos (ex: dentro de CTEs)
        if dangerous_types:
            for d_type in dangerous_types:
                if list(expression.find_all(d_type)):
                    logger.warning(
                        f"Operação proibida detectada na query: {d_type.__name__}"
                    )
                    return False

        # 3. Prevenção extra contra DDLs ocultos em comandos genéricos (ex: GRANT/REVOKE)
        if hasattr(exp, "Command"):
            commands = list(expression.find_all(exp.Command))
            for cmd in commands:
                if not str(cmd).upper().startswith("EXPLAIN"):
                    logger.warning("Comando genérico bloqueado (não é um EXPLAIN).")
                    return False

    return True


def execute_and_validate_sql(
    sql_query: str, con: PostgresBackend, timeout: int = 30
) -> tuple[pa.Table, QueryExecutionStats]:
    """
    Executa uma query gerada pelo LLM diretamente no PostgreSQL via Ibis.

    Transforma a string bruta em uma expressão Ibis e força a execução, retornando os dados em formato binário PyArrow (Zero-Copy).

    Args:
        sql_query (str): A consulta SQL a ser executada.
        con (PostgresBackend): Conexão ativa com o banco PostgreSQL (Ibis).
        timeout (int): Tempo máximo para gerar a query.

    Returns:
        pa.Table: Tabela PyArrow com os resultados da consulta.

    Raises:
        ValueError: Se houver falha na validação ou execução da query no banco.
    """
    stats = QueryExecutionStats(sql_query)
    stats.start()

    try:
        if not sql_query or not sql_query.strip():
            raise ValueError("Query is empty")

        if not is_read_only_query(sql_query):
            logger.critical(f"Tentativa de execução insegura bloqueada:\n{sql_query}")
            raise PermissionError(
                "Query bloqueada: Apenas operações de leitura (SELECT) são permitidas."
            )

        logger.debug(f"Executing SQL:\n{sql_query[:200]}...")

        # con.sql() cria a expressão Ibis a partir da string bruta
        # .to_pyarrow() força a execução e o tráfego binário
        result_table = con.sql(sql_query).to_pyarrow()

        stats.end(rows=result_table.num_rows)
        logger.info(f"Query executada: {stats}")

        return result_table, stats

    except Exception as e:
        stats.error = str(e)
        logger.error(f"Falha na validação/execução do SQL: {e}")
        raise ValueError(f"Erro ao executar a consulta no banco de dados: {e}") from e


def get_query_result_summary(table: pa.Table) -> dict[str, Any]:
    """
    Extrai um resumo das estatísticas sobre o resultado da query, para logging e monitoramento.

    Args:
        table (pa.Table): Resultado em uma tabela PyArrow.

    Returns:
        dict: Resumo das estatísticas.
    """
    return {
        "rows": table.num_rows,
        "columns": table.num_columns,
        "column_names": table.column_names,
        "memory_mb": table.nbytes / (1024 * 1024),
        "schema": str(table.schema),
    }


def safe_execute_sql(
    sql_query: str,
    con: PostgresBackend,
    max_retries: int = 1,
) -> pa.Table | None:
    """
    Executa a query SQL com lógica de repetição.

    Args:
        sql_query (str): SQL Query
        con (PostgresBackend): Conexão com Banco de Dados.
        max_retries (int): Número de tentativas.

    Returns:
        pa.Table or None: Resultados ou None se todas as tentativas falharem.
    """

    for attempt in range(1, max_retries + 1):
        try:
            table, stats = execute_and_validate_sql(sql_query, con)
            logger.info(f"Sucesso na tentiva {attempt}")
            return table

        except Exception as e:
            logger.warning(f"Attempt {attempt}/{max_retries} failed: {e}")

            if attempt == max_retries:
                logger.error(f"Todas as {max_retries} tentativas falharam.")
                return None
    return None


def explain_query(sql_query: str, con: PostgresBackend) -> str:
    """
    Extrai o EXPLAIN para análise de otimização de consultas.

    Args:
        sql_query (str): Query SQL para análise.
        con (PostgresBackend): Conexão do banco de dados.

    Returns:
        str: Saída do EXPLAIN.
    """
    try:
        if not is_read_only_query(sql_query):
            return "Query bloqueada por regras de segurança."

        explain_query_str = f"EXPLAIN {sql_query}"
        result = con.sql(explain_query_str).to_pyarrow()

        explain_list = [
            row["QUERY PLAN"] for row in result.to_pylist() if "QUERY PLAN" in row
        ]
        return "\n".join(explain_list)

    except Exception as e:
        logger.error(f"Falhou ao extrair o EXPLAIN: {e}")
        return f"Não foi possível analisar a query: {e}"
