import logging
from types import FunctionType

import ibis

logger = logging.getLogger(__name__)


def create_metrics_tables(fun: FunctionType, **kwargs) -> ibis.Table:
    """Wrapper que executa a lógica da métrica com tratamento de erro e logs padronizados."""
    metric_name = fun.__name__

    logger.info(f"--- Iniciando cálculo da métrica: {metric_name} ---")

    try:
        result_table = fun(**kwargs)

        logger.info(f"Sucesso ao calcular: {metric_name}.")

        return result_table

    except Exception as e:
        logger.error(f"Falha ao criar métrica {metric_name}: {e}")
        raise e
