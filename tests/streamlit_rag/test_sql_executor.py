from typing import Any
from unittest.mock import MagicMock

import pyarrow as pa
import pytest
from pytest_mock import MockerFixture

from rag_config.sql_executor import (
    QueryExecutionStats,
    execute_and_validate_sql,
    explain_query,
    get_query_result_summary,
    is_read_only_query,
    safe_execute_sql,
)


@pytest.fixture
def mock_postgres_con(mocker: MockerFixture) -> Any:
    """Retorna um mock para a conexão PostgresBackend do Ibis."""
    return mocker.MagicMock()


@pytest.fixture
def sample_pyarrow_table() -> pa.Table:
    """Retorna uma tabela PyArrow simples para testes."""
    return pa.table(
        {
            "id": [1, 2, 3],
            "name": ["Alice", "Bob", "Charlie"],
        }
    )


# ==========================================
# Testes para QueryExecutionStats
# ==========================================
def test_query_execution_stats_success(mocker: MockerFixture) -> None:
    """Testa o fluxo normal de registro de estatísticas de query."""
    mock_time = mocker.patch("rag_config.sql_executor.time.time")

    stats = QueryExecutionStats("SELECT 1")
    assert stats.duration_ms == 0.0

    mock_time.return_value = 100.0
    stats.start()

    mock_time.return_value = 101.5
    stats.end(rows=5)

    assert stats.duration_ms == 1500.0  # (101.5 - 100.0) * 1000
    assert stats.rows_returned == 5
    assert "✅" in str(stats)
    assert "1500.00ms" in str(stats)
    assert "Rows: 5" in str(stats)


def test_query_execution_stats_error(mocker: MockerFixture) -> None:
    """Testa a representação em string quando há erro na execução."""
    stats = QueryExecutionStats("SELECT 1")
    stats.error = "Erro de sintaxe"

    assert "❌" in str(stats)


# ==========================================
# Testes para is_read_only_query
# ==========================================
@pytest.mark.parametrize(
    "query, expected",
    [
        # Consultas válidas de leitura
        ("SELECT * FROM users", True),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", True),
        ("EXPLAIN SELECT * FROM users", True),
        ("EXPLAIN ANALYZE SELECT 1", True),
        ("SELECT id, count(*) FROM sales GROUP BY id", True),
        ("SELECT a FROM t1 UNION SELECT a FROM t2", True),
        # Consultas perigosas (DML/DDL)
        ("UPDATE users SET name = 'admin'", False),
        ("INSERT INTO users (id) VALUES (1)", False),
        ("DELETE FROM logs", False),
        ("DROP TABLE users", False),
        ("ALTER TABLE users ADD COLUMN age INT", False),
        ("CREATE TABLE test (id INT)", False),
        ("TRUNCATE TABLE logs", False),
        ("COMMIT", False),
        ("ROLLBACK", False),
        # DML escondido em CTEs
        ("WITH cte AS (UPDATE users SET age=10 RETURNING *) SELECT * FROM cte", False),
        ("WITH d AS (DELETE FROM t RETURNING id) SELECT * FROM d", False),
        # Erros de Parse / Consultas vazias
        ("", False),
        ("   ", False),
        ("SELECT FROM * INVALID SYNTAX", False),
    ],
)
def test_is_read_only_query_variants(query: str, expected: bool) -> None:
    """Testa a validação AST com diversas queries de leitura e mutação."""
    assert is_read_only_query(query) == expected


def test_is_read_only_query_generic_command() -> None:
    """Testa o bloqueio de comandos genéricos não relacionados a leitura/explain."""
    # O sqlglot frequentemente converte GRANT/REVOKE para Command no dialeto postgres
    assert is_read_only_query("GRANT SELECT ON users TO admin") is False


# ==========================================
# Testes para execute_and_validate_sql
# ==========================================
def test_execute_and_validate_sql_success(
    mock_postgres_con: Any, sample_pyarrow_table: pa.Table
) -> None:
    """Testa a execução de uma query válida retornando o Tabela Arrow e Stats."""
    mock_sql = mock_postgres_con.sql.return_value
    mock_sql.to_pyarrow.return_value = sample_pyarrow_table

    table, stats = execute_and_validate_sql(
        "SELECT * FROM valid_table", mock_postgres_con
    )

    assert isinstance(table, pa.Table)
    assert table.num_rows == 3
    assert stats.rows_returned == 3
    assert stats.error is None
    mock_postgres_con.sql.assert_called_once_with("SELECT * FROM valid_table")
    mock_sql.to_pyarrow.assert_called_once()


def test_execute_and_validate_sql_empty_query(mock_postgres_con: Any) -> None:
    """Testa o lançamento de exceção para query vazia."""
    with pytest.raises(ValueError, match="Query is empty"):
        execute_and_validate_sql("   \n  ", mock_postgres_con)


def test_execute_and_validate_sql_blocked_query(mock_postgres_con: Any) -> None:
    """Testa se queries com mutação são bloqueadas antes de chegar no banco."""
    with pytest.raises(
        ValueError, match="Query bloqueada: Apenas operações de leitura"
    ):
        execute_and_validate_sql("DROP TABLE users", mock_postgres_con)

    mock_postgres_con.sql.assert_not_called()


def test_execute_and_validate_sql_execution_error(mock_postgres_con: Any) -> None:
    """Testa o tratamento de erros provenientes do banco de dados (Ibis)."""
    mock_postgres_con.sql.side_effect = Exception("Table not found")

    with pytest.raises(
        ValueError,
        match="Erro ao executar a consulta no banco de dados: Table not found",
    ):
        execute_and_validate_sql("SELECT * FROM invalid_table", mock_postgres_con)


# ==========================================
# Testes para get_query_result_summary
# ==========================================
def test_get_query_result_summary(sample_pyarrow_table: pa.Table) -> None:
    """Testa a extração de métricas de uma tabela PyArrow."""
    summary = get_query_result_summary(sample_pyarrow_table)

    assert summary["rows"] == 3
    assert summary["columns"] == 2
    assert summary["column_names"] == ["id", "name"]
    assert summary["memory_mb"] > 0
    assert "schema" in summary


# ==========================================
# Testes para safe_execute_sql
# ==========================================
def test_safe_execute_sql_success(
    mocker: MockerFixture, mock_postgres_con: Any
) -> None:
    """Testa o safe_execute_sql completando na primeira tentativa."""
    mock_table = pa.table({"a": [1]})
    mocker.patch(
        "rag_config.sql_executor.execute_and_validate_sql",
        return_value=(mock_table, MagicMock()),
    )

    result = safe_execute_sql("SELECT 1", mock_postgres_con, max_retries=2)
    assert result == mock_table


def test_safe_execute_sql_retry_success(
    mocker: MockerFixture, mock_postgres_con: Any
) -> None:
    """Testa o safe_execute_sql falhando na primeira, mas sucesso na segunda tentativa."""
    mock_table = pa.table({"a": [1]})

    # Efeito colateral: primeira chamada lança erro, segunda retorna a tupla
    mock_execute = mocker.patch("rag_config.sql_executor.execute_and_validate_sql")
    mock_execute.side_effect = [Exception("Timeout na rede"), (mock_table, MagicMock())]

    result = safe_execute_sql("SELECT 1", mock_postgres_con, max_retries=2)

    assert result == mock_table
    assert mock_execute.call_count == 2


def test_safe_execute_sql_all_retries_fail(
    mocker: MockerFixture, mock_postgres_con: Any
) -> None:
    """Testa safe_execute_sql retornando None após esgotar tentativas."""
    mock_execute = mocker.patch(
        "rag_config.sql_executor.execute_and_validate_sql",
        side_effect=Exception("Database down"),
    )

    result = safe_execute_sql("SELECT 1", mock_postgres_con, max_retries=3)

    assert result is None
    assert mock_execute.call_count == 3


# ==========================================
# Testes para explain_query
# ==========================================
def test_explain_query_success(mock_postgres_con: Any) -> None:
    """Testa a geração do plano de execução."""
    # Simula o retorno do PyArrow com a coluna 'QUERY PLAN'
    plan_table = pa.table({"QUERY PLAN": ["Seq Scan on table", "  Filter: (x = 1)"]})
    mock_sql = mock_postgres_con.sql.return_value
    mock_sql.to_pyarrow.return_value = plan_table

    explain_result = explain_query("SELECT * FROM table", mock_postgres_con)

    assert "Seq Scan on table" in explain_result
    assert "Filter: (x = 1)" in explain_result
    mock_postgres_con.sql.assert_called_once_with("EXPLAIN SELECT * FROM table")


def test_explain_query_blocked(mock_postgres_con: Any) -> None:
    """Testa se comandos destrutivos são bloqueados antes de executar o EXPLAIN."""
    result = explain_query("DROP TABLE users", mock_postgres_con)

    assert result == "Query bloqueada por regras de segurança."
    mock_postgres_con.sql.assert_not_called()


def test_explain_query_exception(mock_postgres_con: Any) -> None:
    """Testa o tratamento de erros ao tentar fazer EXPLAIN."""
    mock_postgres_con.sql.side_effect = Exception("Syntax error")

    result = explain_query("SELECT FROM table", mock_postgres_con)

    assert "Não foi possível analisar a query: Syntax error" in result
