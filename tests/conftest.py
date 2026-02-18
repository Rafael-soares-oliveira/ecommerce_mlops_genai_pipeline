import sys
from unittest.mock import MagicMock

from pytest import Session


def pytest_sessionstart(session: Session):
    """
    Executado antes de iniciar a sessão de testes.

    Simula bibliotecas pesadas para evitar ModuleNotFoundError em ambientes onde elas não foram instaladas (como CI rápido).
    """
    # Define quais módulos pesados devem ser ignorados durante os testes
    mock_modules = [
        "torch",
        "sentence_transformers",
    ]
    for module_name in mock_modules:
        sys.modules[module_name] = MagicMock()
