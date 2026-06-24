from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from libs.base.typed_fastapi import TypedFastAPI
from libs.logging.event_utils import track_event_if_configured
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

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

    try:
        # Return configuration values for debugging
        config_dict = {
            "app_logging_enable": config.app_logging_enable,
            "app_logging_level": config.app_logging_level,
            "azure_package_logging_level": config.azure_package_logging_level,
            "azure_logging_packages": config.azure_logging_packages,
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

        track_event_if_configured("GetConfigDebugSuccess", {})
        return JSONResponse(content={"configuration": config_dict})
    except Exception as e:
        track_event_if_configured(
            "GetConfigDebugError",
            {"error": str(e), "error_type": type(e).__name__},
        )
        # Mirror the exception-recording pattern from the other routers
        # so the debug endpoint participates in the same App Insights view.
        span = trace.get_current_span()
        if span is not None and span.is_recording():
            try:
                span.record_exception(e)
                span.set_status(
                    Status(StatusCode.ERROR, description=type(e).__name__)
                )
            except Exception:  # noqa: BLE001
                pass
        raise
