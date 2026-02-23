import logging

import ibis
import polars as pl
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


def execute_sql_query(table: ibis.Table, trigger_execution: bool) -> bool:
    logger.info(f"Criando tabela {table.get_name()}...")
    return trigger_execution


def generate_embeddings(
    table: ibis.Table, model: SentenceTransformer, batch_size: int = 256
) -> pl.DataFrame:
    """
    Gera embeddings de forma vetorizada para a coluna 'chunk_text'.

    Extrai os dados do Ibis para Polars de forma eficiente (via Arrow) e realiza a inferência em lote utilizando o SentenceTransformer. A inserção dos tensores no DataFrame evita cópias desnecessárias na memória.

    Args:
        table (ibis.Table): Tabela Ibis contendo a coluna textual 'chunk_text'.
        model (SentenceTransformer): Instância carregada do modelo de embedding.
        batch_size (int): Tamanho do lote para a inferência. Padrão é 256.

    Returns:
        pl.DataFrame: DataFrame contendo as coluans originais e a nova coluna 'embedding' tipada como pl.Array(pl.Float32).

    Raises:
        TypeError: Se a conversão do PyArrow não retornar um DataFrame Polars.
    """

    logger.info("Iniciando extração do Ibis para Polars...")

    df = pl.from_arrow(table.to_pyarrow())

    if not isinstance(df, pl.DataFrame):
        raise TypeError(
            "A conversão resultou em uma Series, esperava-se um pl.DataFrame."
        )

    logger.info("Iniciando inferência vetorial em lote...")

    embeddings_numpy = model.encode(
        df["chunk_text"].to_list(),
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    # Inserção zero-copy. Evita o .tolist() que consome muita RAM
    df = df.with_columns(
        pl.Series("embedding", embeddings_numpy).cast(pl.Array(pl.Float32, 384))
    )

    # Tratamento de colunas nulas
    null_cols = [c for c in df.columns if df[c].dtype == pl.Null]
    if null_cols:
        df = df.with_columns([pl.col(c).cast(pl.String) for c in null_cols])

    return df


def prepare_products_for_embedding(products: ibis.Table, trigger: bool) -> ibis.Table:
    """Prepara metadados e texto do produto para vetorização."""
    logger.info("Preparando tabela 'products' (Sem Geo)...")

    name = products["name"].fill_null("Unknown")
    brand = products["brand"].fill_null("Unknown")
    category = products["category"].fill_null("Unknown")
    dept = products["department"].fill_null("Unknown")
    price = products["retail_price"].cast("string")

    chunk_text = (
        "Produto: "
        + name
        + ", Marca: "
        + brand
        + ", Categoria: "
        + category
        + ", Depto: "
        + dept
        + ", Preço: $"
        + price
    )

    return products.select(
        source_id=products["id"].cast("int64"),
        chunk_text=chunk_text,
        brand=products["brand"].cast("string"),
        category=products["category"].cast("string"),
        department=products["department"].cast("string"),
        retail_price=products["retail_price"].cast("float64"),
    )


def prepare_users_for_embedding(
    users: ibis.Table, order_items: ibis.Table, trigger: bool
) -> ibis.Table:
    """Prepara metadados de usuários, geolocalização nativa (WKB) e calcula ticket médio."""
    logger.info("Preparando tabela 'users' (Com Geo e Agregação)...")

    # 1. Agrega o gasto médio por usuário direto no banco
    user_spend = order_items.group_by("user_id").aggregate(
        avg_spend=order_items["sale_price"].mean()
    )

    # 2. Join das tabelas
    joined = users.left_join(user_spend, users["id"] == user_spend["user_id"])

    city = joined["city"].fill_null("Unknown")
    state = joined["state"].fill_null("Unknown")
    country = joined["country"].fill_null("Unknown")
    spend_str = joined["avg_spend"].fill_null(0.0).round(2).cast("string")

    # 3. Construção do contexto semântico
    chunk_text = (
        "Cliente localizado em "
        + city
        + ", "
        + state
        + ", "
        + country
        + ". Gasto médio: $"
        + spend_str
    )

    return joined.mutate(
        chunk_text=chunk_text,
        avg_spend=joined.avg_spend.fill_null(0.0).cast("float64"),
    ).select(
        user_id="id",
        city="city",
        state="state",
        country="country",
        latitude="latitude",
        longitude="longitude",
        chunk_text="chunk_text",
        avg_spend="avg_spend",
    )


def fct_user_logistics(  # noqa: PLR0913
    users: ibis.Table,
    orders: ibis.Table,
    order_items: ibis.Table,
    products: ibis.Table,
    distribution_centers: ibis.Table,
    trigger_execution: bool,
) -> bool:
    logger.info("Criando tabela fct_user_logistics...")
    return trigger_execution


def map_hotspots_h3(users: ibis.Table, trigger_execution: bool) -> bool:
    logger.info("Criando tabela map_hotspots_h3...")
    return trigger_execution
