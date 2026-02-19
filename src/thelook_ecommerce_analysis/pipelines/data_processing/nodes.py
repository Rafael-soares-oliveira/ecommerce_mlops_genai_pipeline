import logging
from datetime import UTC, timedelta
from datetime import datetime as datetime_  # Evitar problema com o Linter
from typing import Any

import ibis

from thelook_ecommerce_analysis.pipelines.data_processing.transform_tables import (
    transform_distribution_centers,
    transform_events,
    transform_inventory_items,
    transform_order_items,
    transform_orders,
    transform_products,
    transform_users,
)

logger = logging.getLogger(__name__)


def _validate_ibis_table(table: ibis.Table, rules: dict[str, Any]) -> ibis.Table:
    """
    Valida regras de linha e agregação em um única query eficiente.

    Todo o processamento é feito dentro do banco pelo Ibis.
    """
    metrics = {}

    # 1. Processa regras de linha
    if "row" in rules:
        for name, rule in rules["row"].items():
            metrics[name] = rule(table).cast("int8").fill_null(0).sum().name(name)

    # 2. Processa regras de agregação
    if "agg" in rules:
        for name, rule in rules["agg"].items():
            metrics[name] = rule(table).name(name)

    if not metrics:
        msg = "Regras do Schema da tabela não pode estar vazio."
        logger.error(msg)
        raise ValueError(msg)

    # 3. Executa a query no banco
    results = table.aggregate(**metrics).to_pandas().iloc[0]

    # 4. Verifica falhas (qualquer valor > 0 é erro)
    failures = results[results > 0]

    if not failures.empty:
        error_details = failures.to_dict()
        msg = f"Violação de Contrato Ibis detectada:\n{error_details}"
        logger.error(msg)
        raise ValueError(msg)

    logger.info("Validação Ibis: Sucesso.")
    return table


def extract_users(
    users: ibis.Table, schema_rules: dict[str, Any], columns: list[str]
) -> ibis.Table:
    """
    Extração e limpeza dos dados brutos.

    Args:
        users (Table): Dados brutos a serem transformados.
        schema_rules (dict[str, Any]): Regras do schema para validação.
        columns (str): Colunas que serão utilizadas.

    Returns:
        Table: Dados prontos para ingestão no banco de dados.
    """

    # 1. Seleção de colunas
    df = users.select(columns)

    # 2. Tratamento
    df = transform_users(df)

    # 3. Validação do Schema
    df = _validate_ibis_table(df, schema_rules)

    return df


def extract_distribution_centers(
    dc: ibis.Table, schema_rules: dict[str, Any], columns: list[str]
) -> ibis.Table:
    """
    Extração e limpeza dos dados brutos.

    Args:
        users (Table): Dados brutos a serem transformados.
        schema_rules (dict[str, Any]): Regras do schema para validação.
        columns (str): Colunas que serão utilizadas.

    Returns:
        Table: Dados prontos para ingestão no banco de dados.
    """

    df = dc.select(columns)

    df = transform_distribution_centers(df)

    # 3. Validação do Schema
    df = _validate_ibis_table(df, schema_rules)

    return df


def extract_products(
    products: ibis.Table,
    dc: ibis.Table,
    schema_rules: dict[str, Any],
    columns: list[str],
) -> ibis.Table:
    """Extração e limpeza dos dados brutos."""

    # 1. Seleção de colunas
    df = products.select(columns)

    # 2. Realizar as transformações
    df = transform_products(df)

    # 3. Carrega IDs válidos de Distribution Centers
    try:
        valid_dc_ids = dc.select("id").to_pyarrow()
        # Criamos uma tabela Ibis "virtual" para realizar join entre tabelas de origem distintas (DuckDB x PostgreSQL)
        ref_dc_table = ibis.memtable(valid_dc_ids)
    except Exception as e:
        logger.error(
            f"Erro ao ler distribution_centers. Abortando para evitar erro de FK: {e}"
        )
        raise e

    # 4. Aplicar anti-join para detectar os ids órfãos
    orphans = df.anti_join(ref_dc_table, df.distribution_center_id == ref_dc_table.id)
    orphan_count = orphans.count().to_pyarrow().as_py()

    if orphan_count > 0:
        # Limitar para não poluir o log
        orphan_ids_sample = orphans.select("id").limit(50).to_pyarrow().to_pylist()

        msg = (
            f"INTEGRIDADE REFERENCIAL: {orphan_count} produtos serão removidos pois apontam para distribution_center_id inexistente.\n"
            f"Exemplos de IDs órfãos: {orphan_ids_sample}..."
        )
        logger.warning(msg)

    # 5. Aplicar semi-join para manter apenas os válidos
    df = df.semi_join(ref_dc_table, df.distribution_center_id == ref_dc_table.id)

    # 6. Validação do schema
    df = _validate_ibis_table(df, schema_rules)

    return df


def extract_inventory_items(
    ii: ibis.Table,
    target: ibis.Table,
    dc: ibis.Table,
    schema_rules: dict[str, Any],
    columns: list[str],
) -> ibis.Table:
    """Carga incremental de inventory_items com validação de FK."""

    # 1. Selecionar colunas
    ii = ii.select(columns)

    # 1. Lógica Incremental (Watermark)
    try:
        max_date = target.created_at.max().to_pyarrow().as_py()
        logger.info(f"Última data processada: {max_date}")
    except Exception as e:
        logger.warning(f"Tabela vazia ou ainda não existe: Carga total. Erro: {e}")
        max_date = None

    query = ii
    if max_date:
        query = query.filter(ii.created_at > max_date)

    # 2. Early Exit - Não há dados para inserir
    row_count = query.count().to_pyarrow().as_py()
    if row_count == 0:
        logger.info("Nenhum dado novo. Encerrando Node.")
        return transform_inventory_items(query).limit(0)

    # 3. Tratamento de Tipos
    df = transform_inventory_items(query)

    # 4. Verificação de Integriadade Referencial (FK)
    try:
        dc_ids = dc.select("id").to_pyarrow()
        ref_dc_table = ibis.memtable(dc_ids)
    except Exception as e:
        logger.error(f"Erro ao ler distribution_centers: {e}")
        raise e

    # 4.1. Identifica e Loga órfãos (Anti-join)
    orphans = df.anti_join(
        ref_dc_table, df.product_distribution_center_id == ref_dc_table.id
    )

    orphan_count = orphans.count().to_pyarrow().as_py()
    if orphan_count > 0:
        orphans_sample = (
            orphans.select("product_distribution_center_id")
            .limit(10)
            .to_pyarrow()
            .to_pylist()
        )

        msg = (
            f"INTEGRIDADE REFERENCIAL: {orphan_count} produtos serão removidos pois apontam para distribution_center_id inexistente.\n"
            f"Exemplos de IDs órfãos: {orphans_sample}..."
        )
        logger.warning(msg)

    # 4.2 Filtra apenas os válidos (Semi-join)
    df = df.semi_join(
        ref_dc_table, df.product_distribution_center_id == ref_dc_table.id
    )

    # 5. Validação de Regras de Negócio
    df = _validate_ibis_table(df, schema_rules)

    # 6. Materialização
    return df


def extract_orders(
    orders: ibis.Table,
    users: ibis.Table,
    lookback: int,
    schema_rules: dict[str, Any],
    columns: list[str],
) -> ibis.Table:
    """
    Carga incremental de inventory_items com validação de FK.

    Args:
        orders (Table): Dados brutos a serem inseridos.
        users (Table): Tabela para extrair os IDs
        lookback (int): Pedidos mais velhos que isso não são atualizados.
        schema_rules (dict): Regras de validação do Schema.
        columns (str): Colunas que serão utilizadas.
    """
    # 1. Seleção de colunas
    batch = orders.select(columns)

    # 2. Definição da Moving Window
    cutoff_date = datetime_.now(UTC) - timedelta(days=lookback)
    logger.info(f"Processando pedidos criados a partir de: {cutoff_date}.")

    # 3. Filtra Origem
    batch = batch.filter(batch.created_at >= cutoff_date)

    # Early Exit
    row_count = batch.count().to_pyarrow().as_py()

    if row_count == 0:
        logger.info("Nenhum pedido recente encontrado.")
        return batch.limit(0)

    # 4. Transformação
    df = transform_orders(batch)

    # 5. Integridade Referencial
    try:
        valid_users = ibis.memtable(users.select("id").to_pyarrow())
    except Exception as e:
        raise ValueError(f"Erro ao carregar users IDs: {e}") from e

    # 5.1. Identifica e Loga órfãos (Anti-join)
    orphans = df.anti_join(valid_users, df.user_id == valid_users.id)
    if orphans.count().to_pyarrow().as_py() > 0:
        logger.warning("FK Violation: Pedidos removidos pois user_id não existe.")

    # 5.2 Filtra apenas os válidos (Semi-join)
    df = df.semi_join(valid_users, df.user_id == valid_users.id)

    # 6. Validação
    df = _validate_ibis_table(df, schema_rules)

    final_count = df.count().to_pyarrow().as_py()
    dropped = row_count - final_count

    if dropped > 0:
        logger.warning(
            f"Orders INTEGRIDADE: {dropped} itens removidos por falha de FK ou Schema."
        )

    return df


def extract_order_items(  # noqa: PLR0913
    order_items: ibis.Table,
    orders: ibis.Table,
    users: ibis.Table,
    products: ibis.Table,
    inv_items: ibis.Table,
    lookback: int,
    schema_rules: dict[str, Any],
    columns: list[str],
) -> ibis.Table:
    # 1. Seleção de colunas
    batch = order_items.select(columns)

    # 2. Moving Window
    cutoff_date = datetime_.now(UTC) - timedelta(days=lookback)

    logger.info(f"Processando pedidos criados a partir de {cutoff_date}")

    # 3. Filtra Origem
    batch = batch.filter(batch.created_at >= cutoff_date)

    # Early Exit
    row_count = batch.count().to_pyarrow().as_py()

    if row_count == 0:
        logger.info("Nenhum pedido recente encontrado.")
        return batch.limit(0)

    # 5. Transformação
    df = transform_order_items(batch)

    # 6. Integridade Referencial
    try:
        v_order_id = ibis.memtable(orders.select("order_id").to_pyarrow())
        v_user_id = ibis.memtable(users.select("id").to_pyarrow())
        v_product_id = ibis.memtable(products.select("id").to_pyarrow())
        v_inventory_id = ibis.memtable(inv_items.select("id").to_pyarrow())
    except Exception as e:
        raise ValueError(f"Erro ao carregar FK IDs: {e}") from e

    # 6.1 FK Orders
    df = df.semi_join(v_order_id, df.order_id == v_order_id.order_id)

    # 6.2 FK Users
    df = df.semi_join(v_user_id, df.user_id == v_user_id.id)

    # 6.3 FK Products
    df = df.semi_join(v_product_id, df.product_id == v_product_id.id)

    # 6.4 FK Inventory Items
    df = df.semi_join(v_inventory_id, df.inventory_item_id == v_inventory_id.id)

    final_count = df.count().to_pyarrow().as_py()
    dropped = row_count - final_count

    if dropped > 0:
        logger.warning(
            f"Orders INTEGRIDADE: {dropped} itens removidos por falha de FK ou Schema."
        )

    # 7. Validação
    df = _validate_ibis_table(df, schema_rules)

    return df


def extract_events(
    events: ibis.Table, schema_rules: dict[str, Any], columns: list[str]
) -> ibis.Table:
    """
    Extração e limpeza dos dados brutos.

    Args:
        events (Table): Dados brutos a serem transformados.
        schema_rules (dict[str, Any]): Regras do schema para validação.
        columns (str): Colunas que serão utilizadas.

    Returns:
        Table: Dados prontos para ingestão no banco de dados.
    """

    # 1. Seleção de colunas
    df = events.select(columns)

    # 2. Tratamento
    df = transform_events(df)

    # 3. Validação do Schema
    df = _validate_ibis_table(df, schema_rules)

    return df
