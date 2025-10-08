import datetime
from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

# Application startup time
start_time = datetime.datetime.now()

router = APIRouter(
    tags=["http_probes"],
    responses={404: {"description": "Not found"}},
)


# Default/Root endpoints
@router.get("/")
async def root():
    """Default root endpoint"""
    return JSONResponse(
        content={
            "message": "Code Migration Code converting process API",
            "version": "1.0.0",
            "status": "running",
            "timestamp": datetime.datetime.now().isoformat(),
            "uptime_seconds": (datetime.datetime.now() - start_time).total_seconds(),
        }
    )


@router.get("/health")
async def ImAlive(response: Response):
    # Add Header Name is Custom-Header
    response.headers["Custom-Header"] = "liveness probe"
    return JSONResponse(content={"message": "I'm alive!"})


@router.get("/startup")
async def Startup(response: Response):
    # Add Header Name is Custom-Header
    response.headers["Custom-Header"] = "Startup probe"
    uptime = datetime.datetime.now() - start_time
    hours, remainder = divmod(uptime.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return JSONResponse(
        content={"message": f"Running for {int(hours)}:{int(minutes)}:{int(seconds)}"}
    )
