from sas.cosmosdb.sql.repository import RepositoryBase

from routers.models.process_agent_activities import (
    ProcessStatus,
    ProcessStatusSnapshot,
    AgentStatus,
)


class ProcessStatusRepository(RepositoryBase[ProcessStatus, str]):
    def __init__(self, account_url: str, database_name: str, container_name: str):
        super().__init__(
            account_url=account_url,
            database_name=database_name,
            container_name=container_name,
        )

    async def get_process_status_by_process_id(
        self, process_id: str
    ) -> ProcessStatusSnapshot | None:
        """
        Get the process status by process ID.
        """

        # Get Status by Phase
        status = await self.find_one_async(predicate={"id": process_id})
        if not status:
            return None

        return ProcessStatusSnapshot(
            process_id=status.id,
            step=status.step,
            phase=status.phase,
            status=status.status,
            agents=[
                AgentStatus(
                    name=agent.name,
                    is_currently_speaking=agent.is_currently_speaking,
                    current_action=agent.current_action,
                    last_message=agent.last_message_preview,
                    participating_status=agent.participation_status,
                )
                for agent in status.agents.values()
            ],
        )
