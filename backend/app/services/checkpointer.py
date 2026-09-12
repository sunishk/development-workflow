import os

os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from psycopg import Connection
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings


class CheckpointerManager:
    def __init__(self) -> None:
        self._connection: Connection | None = None
        self._checkpointer: PostgresSaver | None = None

    def start(self) -> PostgresSaver:
        if self._checkpointer is not None:
            return self._checkpointer

        self._connection = Connection.connect(
            settings.langgraph_database_url,
            autocommit=True,
            row_factory=dict_row,
        )
        self._checkpointer = PostgresSaver(self._connection)
        self._checkpointer.setup()
        return self._checkpointer

    @property
    def checkpointer(self) -> PostgresSaver:
        if self._checkpointer is None:
            raise RuntimeError("Checkpointer has not been started")
        return self._checkpointer

    def stop(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._checkpointer = None


checkpointer_manager = CheckpointerManager()
