from unittest.mock import MagicMock

import polars as pl
import pyarrow as pa
import pytest
import streamlit as st
from pytest_mock import MockerFixture

from app import (
    _configure_page,
    _initialize_session_state,
    _render_sidebar,
    fetch_data,
    main,
)


@pytest.fixture(autouse=True)
def reset_session_state() -> None:
    """Limpa o st.session_state antes de cada teste."""
    st.session_state.clear()


def test_configure_page(mocker: MockerFixture) -> None:
    """Testa se a página é configurada corretamente com CSS e título."""
    mock_set_page_config = mocker.patch("app.st.set_page_config")
    mock_markdown = mocker.patch("app.st.markdown")

    _configure_page()

    mock_set_page_config.assert_called_once_with(
        page_title="TheLook Analytics",
        layout="wide",
        page_icon="📊",
        initial_sidebar_state="expanded",
    )
    mock_markdown.assert_called_once()


def test_initialize_session_state(mocker: MockerFixture) -> None:
    """Testa a inicialização das variáveis de sessão."""
    mocker.patch("app.SemanticCache")
    mocker.patch("app.CacheConfig.SEMANTIC_CACHE_THRESHOLD", 0.8)
    mocker.patch("app.CacheConfig.SEMANTIC_CACHE_MAX_HISTORY", 10)
    mocker.patch("app.CacheConfig.QUERY_CACHE_TTL", 3600)

    _initialize_session_state()

    assert "cache" in st.session_state
    assert "messages" in st.session_state
    assert st.session_state.messages == []
    assert "perf_metrics" in st.session_state
    assert st.session_state.perf_metrics == {
        "page_loads": 0,
        "queries_executed": 0,
        "total_time": 0,
    }


def test_fetch_data_success(mocker: MockerFixture) -> None:
    """Testa a execução de query com sucesso, convertendo para DataFrame."""
    st.session_state.perf_metrics = {
        "page_loads": 0,
        "queries_executed": 0,
        "total_time": 0,
    }

    mock_get_db_client = mocker.patch("app.get_db_client")
    mock_con = MagicMock()
    mock_result = MagicMock()

    # Simula retorno do banco como um array PyArrow
    arrow_table = pa.table({"col1": [1, 2], "col2": ["A", "B"]})
    mock_result.to_pyarrow.return_value = arrow_table
    mock_con.sql.return_value = mock_result
    mock_get_db_client.return_value = mock_con

    # Executa a função desembrulhada (ignorando @st.cache_data para o teste unitário)
    df = fetch_data("SELECT * FROM table")

    assert isinstance(df, pl.DataFrame)
    assert df.shape == (2, 2)
    assert st.session_state.perf_metrics["queries_executed"] == 1
    assert st.session_state.perf_metrics["total_time"] >= 0


def test_fetch_data_series_conversion(mocker: MockerFixture) -> None:
    """Testa a execução de query convertendo de Series para DataFrame."""
    st.session_state.perf_metrics = {"queries_executed": 0, "total_time": 0}

    mock_get_db_client = mocker.patch("app.get_db_client")
    mock_con = MagicMock()
    mock_result = MagicMock()

    # Simula retorno de apenas uma coluna (Series no Polars)
    arrow_table = pa.table({"col1": [1, 2, 3]})
    mock_result.to_pyarrow.return_value = arrow_table
    mock_con.sql.return_value = mock_result
    mock_get_db_client.return_value = mock_con

    # Mock pl.from_arrow para forçar o retorno de uma Series diretamente
    mocker.patch("app.pl.from_arrow", return_value=pl.Series("col1", [1, 2, 3]))

    df = fetch_data("SELECT col1 FROM table")

    assert isinstance(df, pl.DataFrame)
    assert df.shape == (3, 1)


def test_fetch_data_exception(mocker: MockerFixture) -> None:
    """Testa o comportamento de erro na execução da query."""
    mocker.patch("app.get_db_client", side_effect=Exception("Database error"))
    mock_st_error = mocker.patch("app.st.error")

    df = fetch_data("SELECT * FROM invalid_table")

    assert isinstance(df, pl.DataFrame)
    assert df.is_empty()
    mock_st_error.assert_called_once_with("Erro na execução da query: Database error")


def test_render_sidebar(mocker: MockerFixture) -> None:
    """Testa a renderização da barra lateral e leitura de métricas."""
    mock_con = MagicMock()
    mock_router = MagicMock()

    mock_router.get_stats.return_value = {
        "num_contexts": 5,
        "model": "model_v1",
        "rag_model": "rag_v1",
        "cache_hits": 2,
    }

    mock_cache = MagicMock()
    mock_cache.get_stats.return_value = {
        "hit_rate": 85.5,
        "entries": 100,
        "total_requests": 150,
    }

    st.session_state.cache = mock_cache
    st.session_state.perf_metrics = {
        "page_loads": 10,
        "queries_executed": 5,
        "total_time": 500,
    }

    mocker.patch("app.st.sidebar.radio", return_value="Métricas")
    mocker.patch("app.st.sidebar.button", return_value=False)

    page = _render_sidebar(mock_con, mock_router)

    assert page == "Métricas"


def test_render_sidebar_clear_cache(mocker: MockerFixture) -> None:
    """Testa a funcionalidade do botão de limpar caches da barra lateral."""
    mock_con = MagicMock()
    mock_router = MagicMock()
    mock_router.get_stats.return_value = {
        "num_contexts": 1,
        "model": "test",
        "rag_model": "test",
        "cache_hits": 0,
    }

    mock_cache = MagicMock()
    mock_cache.get_stats.return_value = {
        "hit_rate": 0,
        "entries": 0,
        "total_requests": 0,
    }

    st.session_state.cache = mock_cache
    st.session_state.messages = ["msg1"]
    st.session_state.perf_metrics = {
        "page_loads": 1,
        "queries_executed": 0,
        "total_time": 0,
    }

    mocker.patch("app.st.sidebar.radio", return_value="Resumo Diário")
    mocker.patch("app.st.sidebar.button", return_value=True)  # Botão pressionado
    mock_st_rerun = mocker.patch("app.st.rerun")
    mock_cache_data_clear = mocker.patch("app.st.cache_data.clear")
    mock_cache_resource_clear = mocker.patch("app.st.cache_resource.clear")

    _render_sidebar(mock_con, mock_router)

    mock_cache.clear.assert_called_once()
    assert len(st.session_state.messages) == 0
    mock_cache_data_clear.assert_called_once()
    mock_cache_resource_clear.assert_called_once()
    mock_st_rerun.assert_called_once()


@pytest.mark.parametrize(
    "page_name, mock_target",
    [
        ("Resumo Diário", "app.render_executive_summary_page"),
        ("Métricas", "app.render_metrics_page"),
        ("Chatbot Analítico", "app.render_chatbot_page"),
    ],
)
def test_main_routing(page_name: str, mock_target: str, mocker: MockerFixture) -> None:
    """Testa o orquestrador principal e o roteamento para cada página."""
    mocker.patch("app._configure_page")

    # Inicializa estado
    st.session_state.perf_metrics = {
        "page_loads": 0,
        "queries_executed": 0,
        "total_time": 0,
    }
    mocker.patch("app._initialize_session_state")

    mock_get_db_client = mocker.patch("app.get_db_client", return_value=MagicMock())
    mock_init_router = mocker.patch("app.init_router", return_value=MagicMock())
    mocker.patch("app._render_sidebar", return_value=page_name)

    mock_page_render = mocker.patch(mock_target)

    main()

    assert st.session_state.perf_metrics["page_loads"] == 1
    mock_get_db_client.assert_called_once()
    mock_init_router.assert_called_once()
    mock_page_render.assert_called_once()
