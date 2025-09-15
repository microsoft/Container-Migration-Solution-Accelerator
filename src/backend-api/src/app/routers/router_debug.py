from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from libs.base.typed_fastapi import TypedFastAPI

router = APIRouter(
    prefix="/debug",
    tags=["debug"],
    responses={404: {"description": "Not found"}},
)


@router.get("/config")
async def get_config_debug(request: Request):
    """Debug endpoint to check configuration values"""
    app: TypedFastAPI = request.app
    config = app.app_context.configuration

    # Return configuration values for debugging
    config_dict = {
        "app_logging_enable": config.app_logging_enable,
        "app_logging_level": config.app_logging_level,
        "cosmos_db_account_url": config.cosmos_db_account_url,
        "cosmos_db_database_name": config.cosmos_db_database_name,
        "cosmos_db_process_container": config.cosmos_db_process_container,
        "cosmos_db_process_log_container": config.cosmos_db_process_log_container,
        "storage_account_name": config.storage_account_name,
        "storage_account_blob_url": config.storage_account_blob_url,
        "storage_account_queue_url": config.storage_account_queue_url,
        "storage_account_process_container": config.storage_account_process_container,
        "storage_account_process_queue": config.storage_account_process_queue,
    }

    return JSONResponse(content={"configuration": config_dict})
