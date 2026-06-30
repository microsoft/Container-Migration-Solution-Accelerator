from fastapi import APIRouter, Request
from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import IDataService, ILoggerService

router = APIRouter(
    prefix="/router_one",
    tags=["router_one"],
    responses={404: {"description": "Not found"}},
)


@router.get("/hello")
def hello(request: Request):
    # Type hint for better IntelliSense support
    app: TypedFastAPI = request.app

    # Get services from dependency injection container with strong typing
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)
    data_service: IDataService = app.app_context.get_service(IDataService)

    # Use the services
    logger_service.log_info("Hello endpoint called")

    # Save some data
    data_service.save_data(
        "last_request", {"endpoint": "/router_one/hello", "timestamp": "now"}
    )

    # Get the data back
    saved_data = data_service.get_data("last_request")

    return {
        "message": "Hello from Router One",
        "configuration_message": app.app_context.configuration.app_sample_variable,
        "saved_data": saved_data,
        "services_registered": len(app.app_context.get_registered_services()),
    }  # Now VS Code will recognize app_context and provide IntelliSense


@router.get("/services")
def get_services(request: Request):
    """Get information about registered services"""
    app: TypedFastAPI = request.app

    # Get logger service to demonstrate service resolution
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)
    logger_service.log_info("Services endpoint called")

    return {
        "registered_services": {
            service_type.__name__: lifetime
            for service_type, lifetime in app.app_context.get_registered_services().items()
        }
    }
