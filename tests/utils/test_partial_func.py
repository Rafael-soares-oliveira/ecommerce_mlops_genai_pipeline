import inspect

import pytest
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis.utils.partial_func import create_node_func


def _sample_processor(df: list[int], multiplier: int) -> list[int]:
    """Processa uma lista de inteiros multiplicando-os."""
    return [x * multiplier for x in df]


class TestCreateNodeFunc:
    """Suíte de testes para validar o wrapper de funções do Kedro. Garante a preservação de metadados e funcionalidade de partials."""

    def test_should_preserve_function_metadata(self) -> None:
        """
        Garante que __name__ e __doc__ são mantidos após o partial.
        Crítico para que o Kedro Viz e os logs identifiquem o nó corretamente.
        """
        original_name = _sample_processor.__name__
        original_doc = _sample_processor.__doc__
        multiplier = 2

        node_func = create_node_func(_sample_processor, multiplier=multiplier)

        # Assert
        assert node_func.__name__ == original_name, "O nome da função foi perdido."
        assert node_func.__doc__ == original_doc, "A docstring foi perdida."

    def test_should_pass_kwargs_correctly(self) -> None:
        """Verifica se os argumentos nomeados (kwargs) são fixados corretamente e se a lógica da função original é preservada."""
        input_data = [10, 20, 30]
        multiplier = 3
        expected_result = [30, 60, 90]

        process_node = create_node_func(_sample_processor, multiplier=multiplier)
        result = process_node(input_data)

        assert result == expected_result, "Os valores deveriam estar multiplicados."

    def test_wrapper_signature_compatibility(self) -> None:
        """Verifica se a função envelopada mantém uma assinatura válida e inspecionável. O Kedro usa `inspect.signature` para validar pipelines na inicialização."""

        def func_with_args(a: int, b: int, c: int = 1) -> int:
            return a + b + c

        wrapped = create_node_func(func_with_args, b=10)
        sig = inspect.signature(wrapped)

        # Verificar se é possível ler os parâmetros
        assert "a" in sig.parameters
        assert "c" in sig.parameters
        assert sig.return_annotation is int

    def test_should_fail_on_missing_arguments(self) -> None:
        """Garante que TypeError é levantado se argumentos obrigatórios (não fixados) não forem fornecidos."""
        # Criar o node sem passar "multiplier", que é obrigatório
        broken_node = create_node_func(_sample_processor)

        with pytest.raises(TypeError) as excinfo:
            broken_node([1, 2, 3])

        assert "argument" in str(excinfo.value)

    def test_interaction_with_mocks(self, mocker: MockerFixture) -> None:
        """Garante compatibilidade com pytest-mock para testes de pipeline."""
        mock_func = mocker.Mock(name="mock_processor")
        mock_func.__name__ = "mock_processor"
        mock_func.return_value = "Sucess"

        wrapped_mock = create_node_func(mock_func, static_arg="fixed")
        result = wrapped_mock("dynamic")

        assert result == "Sucess"
        mock_func.assert_called_once_with("dynamic", static_arg="fixed")
