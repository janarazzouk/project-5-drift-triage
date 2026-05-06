from typing import Any

from sqlalchemy.orm import Session

from app.models.agent_message import AgentMessage


class AgentMessageRepository:
    def create(
        self,
        db: Session,
        *,
        investigation_id: str,
        role: str,
        content: str,
        node_name: str | None = None,
        message_type: str = "summary",
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        record = AgentMessage(
            investigation_id=investigation_id,
            role=role,
            node_name=node_name,
            message_type=message_type,
            content=content,
            metadata_json=metadata,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        return record

    def list_by_investigation(
        self,
        db: Session,
        investigation_id: str,
    ) -> list[AgentMessage]:
        return (
            db.query(AgentMessage)
            .filter(AgentMessage.investigation_id == investigation_id)
            .order_by(AgentMessage.created_at.asc())
            .all()
        )

    def list_recent(
        self,
        db: Session,
        *,
        limit: int = 50,
    ) -> list[AgentMessage]:
        return (
            db.query(AgentMessage)
            .order_by(AgentMessage.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_system_message(
        self,
        db: Session,
        *,
        investigation_id: str,
        content: str,
        node_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        return self.create(
            db,
            investigation_id=investigation_id,
            role="system",
            content=content,
            node_name=node_name,
            message_type="system",
            metadata=metadata,
        )

    def create_agent_message(
        self,
        db: Session,
        *,
        investigation_id: str,
        content: str,
        node_name: str,
        message_type: str = "summary",
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        return self.create(
            db,
            investigation_id=investigation_id,
            role="agent",
            content=content,
            node_name=node_name,
            message_type=message_type,
            metadata=metadata,
        )

    def create_tool_message(
        self,
        db: Session,
        *,
        investigation_id: str,
        content: str,
        node_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentMessage:
        return self.create(
            db,
            investigation_id=investigation_id,
            role="tool",
            content=content,
            node_name=node_name,
            message_type="tool_result",
            metadata=metadata,
        )