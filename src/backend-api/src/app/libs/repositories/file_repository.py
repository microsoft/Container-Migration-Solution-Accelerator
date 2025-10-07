from datetime import datetime, timezone
from sas.cosmosdb.sql.repository import RepositoryBase
from libs.models.entities import File


class FileRepository(RepositoryBase[File, str]):
    def __init__(self, account_url: str, database_name: str, container_name: str):
        super().__init__(
            account_url=account_url,
            database_name=database_name,
            container_name=container_name,
        )

    async def update_async(self, entity: File) -> File:
        # Set the updated_at timestamp to current UTC time
        entity.updated_at = datetime.now(timezone.utc)

        # Call the base class update method
        return await super().update_async(entity)