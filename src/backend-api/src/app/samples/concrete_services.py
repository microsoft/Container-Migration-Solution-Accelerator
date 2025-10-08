from fastapi import APIRouter, Request
from libs.base.typed_fastapi import TypedFastAPI

router = APIRouter(
    prefix="/concrete",
    tags=["concrete_services"],
    responses={404: {"description": "Not found"}},
)


@router.get("/demo")
def concrete_services_demo(request: Request):
    """Demonstrate using concrete services without interfaces"""
    app: TypedFastAPI = request.app

    # You can get concrete services directly if they were registered as concrete classes
    # This would work if you registered them like: app_context.addSingleton(ConsoleLoggerService)

    # For now, let's show how to get services through interfaces
    from libs.services.interfaces import IDataService, ILoggerService

    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)
    data_service: IDataService = app.app_context.get_service(IDataService)

    logger_service.log_info("Concrete services demo endpoint called")

    # Save some data
    data_service.save_data(
        "concrete_demo",
        {
            "message": "This shows how you can use concrete services",
            "pattern": "Both interface-based and concrete class registration work",
        },
    )

    return {
        "message": "Concrete services demo",
        "data_saved": data_service.get_data("concrete_demo"),
        "note": "You can register services either as interfaces or concrete classes",
    }


@router.get("/info")
def service_registration_info():
    """Information about different service registration patterns"""
    return {
        "patterns": {
            "interface_based": {
                "registration": "app_context.addSingleton(IMyService, MyServiceImpl)",
                "usage": "service: IMyService = app_context.get_typed_service(IMyService)",
                "benefits": ["Loose coupling", "Easy testing", "Interface segregation"],
            },
            "concrete_class": {
                "registration": "app_context.addSingleton(MyService)",
                "usage": "service: MyService = app_context.get_typed_service(MyService)",
                "benefits": ["Simpler setup", "Direct access", "No interface needed"],
            },
            "factory_function": {
                "registration": "app_context.addSingleton(IMyService, lambda: MyServiceImpl(config))",
                "usage": "service: IMyService = app_context.get_typed_service(IMyService)",
                "benefits": [
                    "Custom initialization",
                    "Configuration injection",
                    "Complex setup",
                ],
            },
        },
        "examples": [
            "app_context.addSingleton(MyService)  # Concrete class",
            "app_context.add_singlecall(MyService)  # Transient concrete class",
            "app_context.addSingleton(IMyService, MyServiceImpl)  # Interface-based",
            "app_context.addSingleton(IMyService, lambda: MyServiceImpl('config'))  # Factory",
        ],
    }
