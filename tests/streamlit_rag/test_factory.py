import os
from unittest.mock import MagicMock

import pytest
import streamlit as st
from pytest_mock import MockerFixture

from rag_config.factory import CacheConfig, DatabasePool, get_db_client, init_router


@pytest.fixture(autouse=True)
def reset_streamlit_cache() -> None:
    """Limpa o cache do Streamlit antes de cada teste para isolamento."""
    st.cache_resource.clear()


def test_database_pool_singleton() -> None:
    """Testa se a classe DatabasePool implementa corretamente o padrão Singleton."""
    pool1 = DatabasePool()
    pool2 = DatabasePool()
    assert pool1 is pool2


def test_create_connection_success(mocker: MockerFixture) -> None:
    """Testa a criação de conexão com o banco de dados via variáveis de ambiente."""
    mock_backend_instance = MagicMock()
    mock_backend_instance.connect.return_value = "mocked_connection"

    mocker.patch("rag_config.factory.Backend", return_value=mock_backend_instance)

    # Mock das variáveis de ambiente
    mocker.patch.dict(
        os.environ,
        {
            "POSTGRES_HOST": "testhost",
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpassword",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "testdb",
        },
    )

    con = DatabasePool._create_connection()

    mock_backend_instance.connect.assert_called_once_with(
        host="testhost",
        user="testuser",
        password="testpassword",  # noqa: S106
        port=5432,
        database="testdb",
    )
    assert con == "mocked_connection"


def test_create_connection_failure(mocker: MockerFixture) -> None:
    """Testa o comportamento ao falhar a conexão com o banco de dados."""
    mock_backend_instance = MagicMock()
    mock_backend_instance.connect.side_effect = Exception("Falha de rede simulada")
    mocker.patch("rag_config.factory.Backend", return_value=mock_backend_instance)

    with pytest.raises(Exception, match="Falha de rede simulada"):
        DatabasePool._create_connection()


def test_get_db_client(mocker: MockerFixture) -> None:
    """Testa a obtenção do cliente de banco de dados (wrapper com cache)."""
    mock_create_conn = mocker.patch(
        "rag_config.factory.DatabasePool._create_connection",
        return_value="mocked_db_client",
    )

    client1 = get_db_client()
    client2 = get_db_client()

    assert client1 == "mocked_db_client"
    assert client2 == "mocked_db_client"

    # Devido ao @st.cache_resource, deve ser chamado apenas uma vez
    mock_create_conn.assert_called_once()


def test_init_router_success(mocker: MockerFixture) -> None:
    """Testa a inicialização do roteador semântico quando o diretório existe."""
    mocker.patch("rag_config.factory.os.path.exists", return_value=True)
    mock_router_class = mocker.patch("rag_config.factory.InMemorySemanticRouter")
    mock_router_class.return_value = "mocked_router"

    router = init_router()

    assert router == "mocked_router"
    mock_router_class.assert_called_once()


def test_init_router_path_not_found(mocker: MockerFixture) -> None:
    """Testa o comportamento do roteador semântico quando o diretório YAML não existe."""
    mocker.patch("rag_config.factory.os.path.exists", return_value=False)
    mock_st_error = mocker.patch("rag_config.factory.st.error")

    # st.stop lança exception internamente no Streamlit ou encerra a execução
    mock_st_stop = mocker.patch("rag_config.factory.st.stop", side_effect=SystemExit)

    with pytest.raises(SystemExit):
        init_router()

    mock_st_error.assert_called_once()
    mock_st_stop.assert_called_once()


def test_cache_config_log(mocker: MockerFixture) -> None:
    """Testa o método de logging das configurações de cache."""
    mock_logger = mocker.patch("rag_config.factory.logger.info")

    CacheConfig.log_config()

    mock_logger.assert_called_once()
    log_message = mock_logger.call_args[0][0]
    assert "Cache Config: Query=" in log_message
