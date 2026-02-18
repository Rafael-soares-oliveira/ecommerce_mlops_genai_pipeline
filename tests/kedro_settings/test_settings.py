import importlib

from kedro.config import OmegaConfigLoader
from pytest_mock import MockerFixture

from thelook_ecommerce_analysis import settings
from thelook_ecommerce_analysis.hooks import CreateIndexesHook, ResourceMonitoringHook


class TestSettings:
    """Suíte de testes para garantir a integridade das configurações do Kedro (settings.py)."""

    def test_dotenv_is_loaded_on_import(self, mocker: MockerFixture) -> None:
        """Testa que load_dotenv é chamado ao importar as configurações."""
        mock_load = mocker.patch("dotenv.load_dotenv")

        # Força o Python a recarregar o arquivo de settings do zero
        importlib.reload(settings)

        # Valida o side-effect
        mock_load.assert_called_once()

    def test_hooks_instance(self) -> None:
        """Testa se os hooks arquiteturais estão registrados na tupla HOOKS."""
        hooks = settings.HOOKS

        assert isinstance(hooks, tuple), "HOOKS deve ser uma tupla imutável"
        assert len(hooks) == 2, "Esperado exatamente 2 hooks registrados"

        # Validar as instâncias
        has_monitoring = any(isinstance(hook, ResourceMonitoringHook) for hook in hooks)
        has_indexes = any(isinstance(hook, CreateIndexesHook) for hook in hooks)

        assert has_monitoring, "ResourceMonitoringHook não foi registrado"
        assert has_indexes, "CreateIndexesHook não foi registrado"

    def test_config_loader_setup(self) -> None:
        """Testa a injeção do OmegaConfigLoader e a sobreposição de padrões."""
        assert settings.CONFIG_LOADER_CLASS is OmegaConfigLoader, (
            "Deveria ser 'OmegaConfigLoader'"
        )

        args = settings.CONFIG_LOADER_ARGS

        assert args["base_env"] == "base", "Chave 'base_env' deveria ter valor 'base'"
        assert args["default_run_env"] == "local", (
            "Chave 'default_run_env' deveria ter valor 'local'"
        )

        config_patterns = args.get("config_patterns")
        assert isinstance(config_patterns, dict), "'config_patterns' deveria ser dict"

        params = config_patterns.get("parameters")
        assert isinstance(params, list), "'parameters' deveria ser list"
        assert "globals.yml" in params, (
            "O arquivo de variáveis globais deve estar no padrão."
        )
        assert "parameters*" in params, (
            "parameters* deveria estar registrado em 'parameters'"
        )
