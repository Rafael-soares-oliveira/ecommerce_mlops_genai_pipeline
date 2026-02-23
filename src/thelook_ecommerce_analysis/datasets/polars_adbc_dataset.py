import uuid
from typing import Any

import adbc_driver_postgresql.dbapi as pg_adbc
import polars as pl
from kedro.io import AbstractDataset


class PolarsVectorADBCDataset(AbstractDataset[pl.DataFrame, pl.DataFrame]):
    """Dataset para carga de alta performance de vetores e geometrias usando ADBC.

    Este dataset utiliza o driver ADBC para transferir dados via Apache Arrow,
    permitindo conversões eficientes para tipos pgvector e PostGIS através de
    uma tabela de staging intermediária.

    Attributes:
        _connection_url: String de conexão do banco de dados.
        _table_name: Nome da tabela de destino.
        _schema: Schema do banco de dados.
        _has_geo: Se deve processar colunas geográficas.
    """

    def __init__(
        self,
        credentials: dict[str, Any],
        table_name: str,
        schema: str = "public",
        has_geo: bool = False,
        metadata: dict[str, Any] | None = None,
    ):
        """Inicializa o dataset.

        Args:
            credentials: Dicionário contendo a chave 'con' com a URL de conexão.
            table_name: Nome da tabela alvo.
            schema: Nome do schema alvo.
            has_geo: Se True, tenta converter a coluna 'user_geom' para geography.
        """
        self._connection_url = credentials["con"]
        self._table_name = table_name
        self._schema = schema
        self._has_geo = has_geo

    def _load(self) -> pl.DataFrame:
        """Carrega os dados da tabela para um DataFrame Polars.

        Returns:
            pl.DataFrame: Conteúdo da tabela.
        """
        query = f"SELECT * FROM {self._schema}.{self._table_name}"  # noqa: S608
        with pg_adbc.connect(self._connection_url) as conn:
            return pl.read_database(query=query, connection=conn)

    def _ensure_dataframe(self, data: Any) -> pl.DataFrame:
        """Garante a conversão para DataFrame, tratando InProcessQuery.

        Args:
            data: Objeto que pode ser DataFrame, LazyFrame ou InProcessQuery.

        Returns:
            pl.DataFrame: O dado materializado em memória.
        """
        if isinstance(data, pl.LazyFrame):
            # Forçamos a coleta. Se o retorno não for DataFrame,
            # lidamos com o objeto de query abaixo.
            data = data.collect()

        # InProcessQuery possui o método to_dataframe()
        if hasattr(data, "to_dataframe"):
            return data.to_dataframe()

        if isinstance(data, pl.DataFrame):
            return data

        # Fallback para tentar converter qualquer outro iterável/objeto
        return pl.DataFrame(data)

    def _save(self, data: pl.DataFrame | pl.LazyFrame) -> None:
        """Salva o DataFrame realizando casts para vetores e geo através de staging.

        Args:
            data: DataFrame ou LazyFrame do Polars.

        Raises:
            Exception: Caso ocorra erro durante a transação de staging.
        """
        # Materialização robusta
        df = self._ensure_dataframe(data)

        # Identificadores únicos e seguros

        temp_table = f"staging_{uuid.uuid4().hex[:8]}"
        full_target_table = f"{self._schema}.{self._table_name}"

        with pg_adbc.connect(self._connection_url) as conn:
            # 1. Carga de altíssima velocidade (Arrow -> Postgres) na Staging
            df.write_database(
                table_name=temp_table,
                connection=conn,
                engine="adbc",
                if_table_exists="replace",
            )

            # 2. Prepara os Casts para Vector e PostGIS
            columns = df.columns
            select_cols = []
            target_cols = []

            for col in columns:
                if col == "embedding":
                    # Converte o array nativo do Postgres {} para o padrão do pgvector []
                    select_cols.append(
                        f"REPLACE(REPLACE(\"{col}\"::text, '{{', '['), '}}', ']')::vector"
                    )
                    target_cols.append(f'"{col}"')
                elif col in ["latitude", "longitude"] and self._has_geo:
                    # Ignora lat/lon no loop principal, pois serão unidas depois
                    pass
                elif col == "user_geom":
                    # Ignora caso exista um user_geom residual
                    pass
                else:
                    select_cols.append(f'"{col}"')
                    target_cols.append(f'"{col}"')

            # Cria a geometria PostGIS nativa a partir da staging table
            if self._has_geo and "latitude" in columns and "longitude" in columns:
                select_cols.append(
                    'ST_SetSRID(ST_MakePoint("longitude", "latitude"), 4326)::geography'
                )
                target_cols.append('"user_geom"')

            select_clause = ", ".join(select_cols)
            target_cols_clause = ", ".join(target_cols)

            insert_query = f"""
                INSERT INTO {full_target_table} ({target_cols_clause})
                SELECT {select_clause} FROM "{temp_table}";
            """  # noqa: S608
            drop_query = f'DROP TABLE IF EXISTS "{temp_table}";'

            # 3. Executa o Insert interno com tratamento seguro de transação
            try:
                with conn.cursor() as cur:
                    cur.execute(insert_query)
                conn.commit()
            except Exception as e:
                # Em caso de erro, fazemos o rollback para destravar a conexão
                conn.rollback()
                raise e
            finally:
                # O bloco finally garante que a tabela de staging será apagada
                # independentemente do sucesso ou falha do INSERT anterior.
                try:
                    with conn.cursor() as cur:
                        cur.execute(drop_query)
                    conn.commit()
                except Exception:  # noqa: S110
                    pass

    def _describe(self) -> dict[str, Any]:
        """Retorna os metadados do dataset.

        Returns:
            Dict[str, Any]: Dicionário com table, schema e engine.
        """
        return {
            "table": self._table_name,
            "schema": self._schema,
            "has_geo": self._has_geo,
            "engine": "adbc",
        }
