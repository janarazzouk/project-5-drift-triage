from app.clients.agent_client import AgentClient
from app.schemas.job import JobResultPayload


class NotificationService:
    def __init__(
        self,
        agent_client: AgentClient,
    ):
        self.agent_client = agent_client

    def notify_agent(
        self,
        payload: JobResultPayload,
    ) -> dict:
        return self.agent_client.send_job_result(payload)