from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class CheckpointService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._context: Any | None = None
        self._checkpointer: Any | None = None

    def setup(self) -> None:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            with PostgresSaver.from_conn_string(
                self.settings.langgraph_checkpoint_db_uri
            ) as checkpointer:
                checkpointer.setup()

            logger.info("LangGraph Postgres checkpoint tables are ready.")
        except Exception as exc:
            logger.warning(
                "Could not initialize LangGraph checkpoint tables.",
                extra={"error": str(exc)},
            )

    def get_checkpointer(self) -> Any:
        if self._checkpointer is not None:
            return self._checkpointer

        from langgraph.checkpoint.postgres import PostgresSaver

        self._context = PostgresSaver.from_conn_string(
            self.settings.langgraph_checkpoint_db_uri
        )
        self._checkpointer = self._context.__enter__()

        return self._checkpointer

    def close(self) -> None:
        if self._context is not None:
            self._context.__exit__(None, None, None)
            self._context = None
            self._checkpointer = None

    def build_config(self, thread_id: str) -> dict[str, Any]:
        return {
            "configurable": {
                "thread_id": thread_id,
            }
        }