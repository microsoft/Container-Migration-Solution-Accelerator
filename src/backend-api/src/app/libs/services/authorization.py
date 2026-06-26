from fastapi import HTTPException

from libs.base.typed_fastapi import TypedFastAPI
from libs.models.entities import Process
from libs.repositories.process_repository import ProcessRepository


async def verify_process_ownership(
    app: TypedFastAPI, process_id: str, user_id: str
) -> Process:
    """Ensure the authenticated caller owns the requested process.

    Fetches the Process entity and compares its stored ``user_id`` against the
    authenticated caller. A missing process and a process owned by a different
    user are treated identically and both raise a 404, so callers cannot probe
    for the existence of other users' processes.

    Args:
        app: The FastAPI application carrying the dependency-injection context.
        process_id: The identifier of the process being accessed.
        user_id: The authenticated caller's user principal id.

    Returns:
        The owned Process entity.

    Raises:
        HTTPException: 404 if the process does not exist or is not owned by the
            authenticated caller.
    """
    if not process_id:
        raise HTTPException(status_code=400, detail="Process ID is required")

    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")

    async with app.app_context.create_scope() as scope:
        process_repository = scope.get_service(ProcessRepository)
        process = await process_repository.get_async(process_id)

    if not process or process.user_id != user_id:
        # Return 404 (not 403) so the response does not confirm the existence of
        # processes belonging to other users.
        raise HTTPException(status_code=404, detail="Process not found")

    return process
