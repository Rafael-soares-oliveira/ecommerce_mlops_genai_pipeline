import logging
import uuid
from typing import Any

import ibis.expr.types as ir
from kedro_datasets.ibis import TableDataset
from pgpq import ArrowToPostgresBinaryEncoder
from sqlalchemy import (
    URL,
    Engine,
    create_engine,
    text,
)

logger = logging.getLogger(__name__)


class IbisUpsertDataset(TableDataset):
    """Extensão do Ibis TableDataset para suportar UPSERT via pgpq."""

    def __init__(self, *args, **kwargs) -> None:
        save_args = kwargs.get("save_args", {})
        self._is_upsert = False

        if save_args.get("mode") == "upsert":
            self._is_upsert = True
            save_args["mode"] = "append"
            kwargs["save_args"] = save_args

        super().__init__(*args, **kwargs)

    def _ensure_list(self, value: str | list[str] | None) -> list[str]:
        """Helper para garantir que o input seja sempre uma lista."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value

    def _get_sqlalchemy_engine(self) -> Engine:
        if hasattr(self.connection, "engine"):
            return self.connection.engine

        conf = self._connection_config.copy()
        conf.pop("backend", None)

        return create_engine(
            URL.create(
                drivername="postgresql+psycopg",
                username=conf.get("user") or conf.get("username"),
                password=conf.get("password"),
                host=conf.get("host"),
                port=conf.get("port"),
                database=conf.get("database") or conf.get("dbname"),
            )
        )

    def save(self, data: ir.Table) -> None:
        if not self._is_upsert:
            return super().save(data)

        # 1. Configuração (Factory Pattern)
        global_config = self._save_args.get("global_config")
        specific_config = {}

        if global_config and isinstance(global_config, dict):
            # O Kedro/Ibis define self._table_name no __init__
            if self._table_name in global_config:
                specific_config = global_config.get(self._table_name)
            else:
                logger.warning(
                    f"Tabela '{self._table_name}' não encontrada no global_config. Usando defaults."
                )

        def get_arg(key: str, default: Any = None) -> Any:
            if key in specific_config:
                return specific_config[key]
            return self._save_args.get(key, default)

        # 2. Materialização (Zero-Copy)
        arrow_table = data.to_pyarrow()
        if arrow_table.num_rows == 0:
            logger.info(f"Tabela {self._table_name}: Vazia.")
            return

        # 3. Filtragem de Colunas (Evita erro de INSERT mismatch)
        target_columns = self._ensure_list(get_arg("columns"))

        if target_columns:
            missing = set(target_columns) - set(arrow_table.column_names)
            if missing:
                raise ValueError(
                    f"Colunas configuradas ausentes no input {self._table_name}: {missing}"
                )
            arrow_table = arrow_table.select(target_columns)

        # 4. Garantia de Schema (DDL)
        engine = self._get_sqlalchemy_engine()

        # 5. Preparação dos Metadados SQL
        cols = arrow_table.column_names
        cols_sql = [f'"{c}"' for c in cols]

        index_elements = self._ensure_list(get_arg("index_elements", ["id"]))
        exclude_from_update = self._ensure_list(get_arg("exclude_from_update", []))

        update_cols = [
            c for c in cols if c not in index_elements and c not in exclude_from_update
        ]

        # Monta o SET: "coluna" = EXCLUDED."coluna"
        set_clause_parts = [f'"{c}" = EXCLUDED."{c}"' for c in update_cols]

        # Monta o WHERE: Verifica se alguma coisa mudou
        # "tabela"."col" IS DISTINCT FROM EXCLUDED."col"
        where_clause_parts = [
            f'"{self._table_name}"."{c}" IS DISTINCT FROM EXCLUDED."{c}"'
            for c in update_cols
        ]

        idx_sql = ", ".join([f'"{i}"' for i in index_elements])

        if not update_cols:
            # Se não tem colunas para atualizar, apenas ignora conflitos
            on_conflict = "DO NOTHING"
        else:
            # Upsert inteligente: Só atualiza SE houver diferença
            on_conflict = f"""
                DO UPDATE SET {", ".join(set_clause_parts)}
                WHERE {" OR ".join(where_clause_parts)}
            """

        schema = self._connection_config.get("schema") or "public"

        temp_table = f"tmp_{self._table_name}_{uuid.uuid4().hex[:8]}"

        # 6. Execução Transacional (Upsert)
        with engine.begin() as conn:
            # A. Cria Temp Table
            conn.execute(
                text(f"""
                CREATE TEMP TABLE {temp_table}
                (LIKE {schema}."{self._table_name}" INCLUDING DEFAULTS)
                ON COMMIT DROP
            """)
            )

            # B. Encoder Arrow -> Binary
            encoder = ArrowToPostgresBinaryEncoder(arrow_table.schema)

            # C. Injeção Binária
            raw_conn = conn.connection.driver_connection
            if raw_conn is None:
                raise ValueError("Falha na conexão nativa psycopg.")

            with raw_conn.cursor() as cursor:
                copy_sql = f"COPY {temp_table} ({', '.join(cols_sql)}) FROM STDIN WITH (FORMAT BINARY)"

                with cursor.copy(copy_sql) as copy:
                    copy.write(encoder.write_header())
                    for batch in arrow_table.to_batches():
                        copy.write(encoder.write_batch(batch))
                    copy.write(encoder.finish())

            # D. Merge Final
            upsert_sql = f"""
                INSERT INTO {schema}."{self._table_name}" ({", ".join(cols_sql)})
                SELECT {", ".join(cols_sql)} FROM {temp_table}
                ON CONFLICT ({idx_sql})
                {on_conflict}
            """  # noqa: S608

            result = conn.execute(text(upsert_sql))

            logger.info(
                f"UPSERT concluído em {self._table_name}: {result.rowcount} de {arrow_table.num_rows} linhas inseridas."
            )
