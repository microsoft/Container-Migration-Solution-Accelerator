from fastapi import APIRouter, Request
from libs.base.typed_fastapi import TypedFastAPI
from libs.services.interfaces import IHttpService, ILoggerService

router = APIRouter(
    prefix="/router_two",
    tags=["router_two"],
    responses={404: {"description": "Not found"}},
)


@router.get("/hello")
def hello(request: Request):
    """Basic hello endpoint"""
    app: TypedFastAPI = request.app

    # Get logger service
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)
    logger_service.log_info("Router Two hello endpoint called")

    return {"message": "Hello from Router Two"}


@router.get("/test-transient")
def test_transient_service(request: Request):
    """Test transient service - should create new instances each time"""
    app: TypedFastAPI = request.app

    # Get two instances of the transient service
    http_service1: IHttpService = app.app_context.get_service(IHttpService)
    http_service2: IHttpService = app.app_context.get_service(IHttpService)

    # Get singleton service instances
    logger_service1: ILoggerService = app.app_context.get_service(ILoggerService)
    logger_service2: ILoggerService = app.app_context.get_service(ILoggerService)

    logger_service1.log_info("Testing service lifetimes")

    return {
        "message": "Service lifetime test",
        "transient_instances_same": id(http_service1)
        == id(http_service2),  # Should be False
        "singleton_instances_same": id(logger_service1)
        == id(logger_service2),  # Should be True
        "transient_instance_ids": [id(http_service1), id(http_service2)],
        "singleton_instance_ids": [id(logger_service1), id(logger_service2)],
    }
