from typing import Any

import sqlglot
from kedro.io import AbstractDataset, DatasetError
from sqlalchemy import create_engine, text


class PostGISScriptDataset(AbstractDataset):
    """
    Kedro Dataset para execução restrita de comandos DDL (CREATE) e COMMENT.

    Este dataset garante que apenas a criação de objetos (tabelas, índices,
    views) e a adição de comentários sejam permitidas no script SQL.

    Attributes:
        ALLOWED_EXPRESSIONS: Tupla de classes do sqlglot permitidas.

    Example:
        >>> dataset = PostGISScriptDataset(
        ...     sql_script="path/to/script.sql",
        ...     credentials={"con": "postgresql://user:pass@host:port/db"},
        ... )
        >>> dataset.load(params={"schema_name": "public"})
    """

    ALLOWED_EXPRESSIONS = (sqlglot.exp.Create, sqlglot.exp.Comment)

    def __init__(
        self,
        sql_script: str,
        credentials: dict,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Inicializa o dataset com o script e as credenciais.

        Args:
            sql_script: Caminho para o arquivo .sql.
            credentials: Dicionário com a chave 'con' para o SQLAlchemy.
        """
        self._sql_path = sql_script
        self._credentials = credentials

    def _validate_sql(self, sql_content: str) -> None:
        """
        Valida se o SQL contém apenas comandos permitidos.

        Args:
            sql_content: Conteúdo bruto do SQL.

        Raises:
            DatasetError: Se houver qualquer comando que não seja CREATE OU COMMENT.
        """
        try:
            expressions = sqlglot.parse(sql_content, read="postgres")

            for expression in expressions:
                if expression is None:
                    continue
                if not isinstance(expression, self.ALLOWED_EXPRESSIONS):
                    cmd_name = expression.key.upper()
                    raise DatasetError(
                        f"Ação negada: O comando '{cmd_name}' não é permitido. "
                        "Este dataset aceita apenas CREATE e COMMENT."
                    )

        except sqlglot.errors.ParseError as e:
            raise DatasetError(f"Erro de sintaxe no SQL: {e}") from e

    def _load(self, params: dict[str, Any] | None = None) -> bool:
        """
        Executa o script validando no banco de dados.

        Args:
            params: Parâmetros para bind variables (ex: :table_name).

        Returns:
            bool: True se a execução ocorrer com sucesso.
        """

        with open(self._sql_path) as f:
            sql_content = f.read()

        self._validate_sql(sql_content)

        engine = create_engine(self._credentials["con"])

        with engine.connect() as conn:
            conn.execute(text(sql_content), params or {})
            conn.commit()
        return True

    def _save(self, data: Any):
        """Operação não suportada."""
        raise DatasetError(
            "Este dataset é apenas para execução de scripts (read-only)."
        )

    def _describe(self) -> dict:
        """Descreve o dataset."""
        return dict(sql_path=self._sql_path)
