import os

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "").rstrip("/")

# Read allowed origins from environment; fall back to same-origin only
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Build paths
BUILD_DIR = os.path.join(os.path.dirname(__file__), "dist")
INDEX_HTML = os.path.join(BUILD_DIR, "index.html")

# Serve static files from build directory
app.mount(
    "/assets", StaticFiles(directory=os.path.join(BUILD_DIR, "assets")), name="assets"
)


@app.get("/")
async def serve_index():
    return FileResponse(INDEX_HTML)


@app.get("/config")
async def get_config(request: Request):
    # Only serve config to same-origin requests by checking the Referer/Origin
    origin = request.headers.get("origin") or ""
    referer = request.headers.get("referer") or ""
    host = request.headers.get("host") or ""
    if origin and not origin.endswith(host):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    config = {
        "API_URL": os.getenv("API_URL", ""),
        "REACT_APP_MSAL_AUTH_CLIENTID": os.getenv(
            "REACT_APP_MSAL_AUTH_CLIENTID", ""
        ),
        "REACT_APP_MSAL_AUTH_AUTHORITY": os.getenv(
            "REACT_APP_MSAL_AUTH_AUTHORITY", ""
        ),
        "REACT_APP_MSAL_REDIRECT_URL": os.getenv(
            "REACT_APP_MSAL_REDIRECT_URL", ""
        ),
        "REACT_APP_MSAL_POST_REDIRECT_URL": os.getenv(
            "REACT_APP_MSAL_POST_REDIRECT_URL", ""
        ),
        "REACT_APP_WEB_SCOPE": os.getenv(
            "REACT_APP_WEB_SCOPE", ""
        ),
        "REACT_APP_API_SCOPE": os.getenv(
            "REACT_APP_API_SCOPE", ""
        ),
        "ENABLE_AUTH": os.getenv("ENABLE_AUTH", "false"),
    }
    return config


@app.api_route("/api/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_api(full_path: str, request: Request):
    if not BACKEND_API_URL:
        return JSONResponse(status_code=503, content={"detail": "Backend API URL is not configured"})

    target_url = f"{BACKEND_API_URL}/api/{full_path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)

    body = await request.body()

    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
        proxied = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )

    passthrough_headers = {
        key: value
        for key, value in proxied.headers.items()
        if key.lower() not in {"content-encoding", "transfer-encoding", "connection"}
    }

    return Response(
        content=proxied.content,
        status_code=proxied.status_code,
        headers=passthrough_headers,
        media_type=proxied.headers.get("content-type"),
    )


@app.get("/{full_path:path}")
async def serve_app(full_path: str):
    # Resolve the requested path and ensure it stays within BUILD_DIR
    file_path = os.path.realpath(os.path.join(BUILD_DIR, full_path))
    build_dir_real = os.path.realpath(BUILD_DIR)
    if not file_path.startswith(build_dir_real + os.sep) and file_path != build_dir_real:
        return FileResponse(INDEX_HTML)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    # Otherwise serve index.html for client-side routing
    return FileResponse(INDEX_HTML)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3000)
