import pytest
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis.pipelines.data_metrics.nodes import (
    create_metrics_tables,
)


# Funções fictícias para injetar no wrapper
def dummy_success_func(param1: str) -> str:
    return f"tabela_{param1}"


def dummy_error_func() -> None:
    raise ValueError("Erro simulado")


def test_create_metrics_tables_success(mocker: MockerFixture):
    # Intercepta os logs de info
    mock_logger_info = mocker.patch(
        "thelook_ecommerce_analysis.pipelines.data_metrics.nodes.logger.info"
    )

    # Executa o wrapper
    result = create_metrics_tables(dummy_success_func, param1="teste")

    # Valida o retorno e as chamadas de log
    assert result == "tabela_teste"
    mock_logger_info.assert_any_call(
        "--- Iniciando cálculo da métrica: dummy_success_func ---"
    )
    mock_logger_info.assert_any_call("Sucesso ao calcular: dummy_success_func.")


def test_create_metrics_tables_failure(mocker: MockerFixture):
    # Intercepta os logs de erro
    mock_logger_error = mocker.patch(
        "thelook_ecommerce_analysis.pipelines.data_metrics.nodes.logger.error"
    )

    # Valida se a exceção correta é propagada
    with pytest.raises(ValueError, match="Erro simulado"):
        create_metrics_tables(dummy_error_func)

    # Valida se o erro foi logado corretamente
    mock_logger_error.assert_called_once_with(
        "Falha ao criar métrica dummy_error_func: Erro simulado"
    )
