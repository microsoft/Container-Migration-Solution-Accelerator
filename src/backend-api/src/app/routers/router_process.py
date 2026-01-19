import io
import zipfile
from enum import Enum
from typing import List, Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from libs.base.typed_fastapi import TypedFastAPI
from libs.models.entities import Process
from libs.repositories.process_repository import ProcessRepository
from libs.services.auth import get_authenticated_user
from libs.services.interfaces import ILoggerService
from libs.services.process_services import ProcessService
from routers.models.files import FileInfo
from routers.models.processes import (
    FileContentResponse,
    ProcessCreateResponse,
    ProcessInfo,
    ProcessSummaryFileInfo,
    ProcessSummaryResponse,
    enlist_process_queue_response,
)
from routers.models.processes import (
    FileInfo as ResponseFileInfo,
)

router = APIRouter(
    prefix="/api/process",
    tags=["process"],
    responses={404: {"description": "Not found"}},
)


class process_router_paths(str, Enum):
    UPLOAD_FILES = "/upload"
    START_PROCESSING = "/start-processing"
    DELETE_FILE = "/delete-file/{file_name}"
    DELETE_PROCESS = "/delete-process/{process_id}"
    CANCEL_PROCESS = "/cancel/{process_id}"
    CANCEL_STATUS = "/cancel/{process_id}/status"
    STATUS = "/status/{process_id}/"
    RENDER_STATUS = "/status/{process_id}/render/"
    PROCESS_AGENT_ACTIVITIES = "/status/{process_id}/activities"


@router.get(process_router_paths.PROCESS_AGENT_ACTIVITIES, response_model=Process)
@router.post("/create")
async def create(request: Request):
    app: TypedFastAPI = request.app
    logger: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        process = Process(id=str(uuid4()), user_id=user_id)

        async with app.app_context.create_scope() as scope:
            processRepository = scope.get_service(ProcessRepository)
            await processRepository.add_async(process)

        return ProcessCreateResponse(process_id=process.id)
    except HTTPException as e:
        logger.log_error(f"HTTPException: {e.detail}", e)
        raise e
    except Exception as e:
        logger.log_error(f"Exception: {str(e)}", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/status/{process_id}/")
async def status(process_id: str, request: Request):
    """Check the status of the process router for a specific process"""
    app: TypedFastAPI = request.app

    logger_service = app.app_context.get_service(ILoggerService)
    logger_service.log_info(
        f"Process router status endpoint called for process_id: {process_id}"
    )

    # loading business component for process
    processService = app.app_context.get_service(ProcessService)

    return await processService.get_current_process(process_id)


@router.get("/status/{process_id}/render/", response_class=JSONResponse)
async def render_status(process_id: str, request: Request):
    """Render the status of the process router for a specific process"""
    app: TypedFastAPI = request.app

    logger_service = app.app_context.get_service(ILoggerService)
    logger_service.log_info(
        f"Process router render status endpoint called for process_id: {process_id}"
    )

    # loading business component for process
    processService = app.app_context.get_service(ProcessService)

    return await processService.render_current_process(process_id)


@router.post(process_router_paths.UPLOAD_FILES, status_code=200)
async def upload_files(
    process_id: str = Form(..., description="Process ID from /create endpoint"),
    files: List[UploadFile] = File(..., description="List of files to upload"),
    request: Request = None,
    response: Response = None,
):
    """
    Upload files to an existing process created by /create endpoint.
    This endpoint accepts a process_id and multiple files, and saves them to Azure Blob Storage.
    Use /start-processing endpoint after this to begin the migration workflow.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info("Upload Files endpoint called")

        # Validate
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate process_id is provided
        if not process_id:
            raise HTTPException(status_code=400, detail="Process ID is required")

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Make uploaded files list
        uploaded_files: list[FileInfo] = []

        for file in files:
            if not file.filename:
                continue  # Skip files without a name

            # Read file content
            content = await file.read()
            file_info = FileInfo(
                filename=file.filename,
                content=content,
                content_type=file.content_type or "application/octet-stream",
                size=len(content),
            )
            uploaded_files.append(file_info)

            await file.seek(0)  # Reset file pointer for further processing

        # Save files to Azure Blob Storage
        processService = app.app_context.get_service(ProcessService)

        await processService.save_files_to_blob(
            process_id=process_id, files=uploaded_files
        )

        logger_service.log_info(
            f"Uploaded {len(uploaded_files)} files for process {process_id}"
        )

        # Get ALL files for this process (including previously uploaded files)
        all_process_files = await processService.get_all_uploaded_files(process_id)

        logger_service.log_info(
            f"Total files for process {process_id}: {len(all_process_files)}"
        )

        # Create result response with ALL files for this process
        result_response = enlist_process_queue_response(
            message="Files uploaded successfully",
            user_id=str(user_id),
            process_id=process_id,
            files=[
                ResponseFileInfo(
                    filename=file_info.filename,
                    content_type=file_info.content_type,
                    size=file_info.size,
                )
                for file_info in all_process_files
            ],
        )

        # Add Header to process status url
        if response:
            response.headers["Location"] = f"/process/{process_id}/"

        return result_response
    except Exception as e:
        logger_service.log_error(f"Error in upload_files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading files: {str(e)}")


@router.delete(process_router_paths.DELETE_FILE, status_code=200)
async def delete_file(
    file_name: str,
    process_id: str = Form(..., description="Process ID from /create endpoint"),
    request: Request = None,
    response: Response = None,
):
    """
    Delete a specific file from an existing process.
    This endpoint removes a file from the {process_id}/source/ folder in Azure Blob Storage.
    Returns the updated list of all remaining files for the process.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(f"Delete File endpoint called for file: {file_name}")

        # Validate process_id is provided
        if not process_id:
            raise HTTPException(status_code=400, detail="Process ID is required")

        # Validate file_name is provided
        if not file_name:
            raise HTTPException(status_code=400, detail="File name is required")

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get process service
        processService = app.app_context.get_service(ProcessService)

        # Delete the specific file from blob storage
        await processService.delete_file_from_blob(process_id, file_name)

        logger_service.log_info(f"Deleted file {file_name} from process {process_id}")

        # Get ALL remaining files for this process after deletion
        all_process_files = await processService.get_all_uploaded_files(process_id)

        logger_service.log_info(
            f"Remaining files for process {process_id}: {len(all_process_files)}"
        )

        # Create result response with ALL remaining files for this process
        result_response = enlist_process_queue_response(
            message="File deleted successfully",
            user_id=str(user_id),
            process_id=process_id,
            files=[
                ResponseFileInfo(
                    filename=file_info.filename,
                    content_type=file_info.content_type,
                    size=file_info.size,
                )
                for file_info in all_process_files
            ],
        )

        # Add Header to process status url
        if response:
            response.headers["Location"] = f"/process/{process_id}/"

        return result_response

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"File '{file_name}' not found for process '{process_id}'",
        )
    except Exception as e:
        logger_service.log_error(f"Error in delete_file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")


@router.delete(process_router_paths.DELETE_PROCESS, status_code=200)
async def delete_process(
    process_id: str,
    request: Request = None,
    response: Response = None,
):
    """
    Delete all files for a specific process.
    This endpoint removes all files from the {process_id}/source/ folder in Azure Blob Storage.
    Returns an empty file list after successful deletion.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(
            f"Delete Process endpoint called for process: {process_id}"
        )

        # Validate process_id is provided
        if not process_id:
            raise HTTPException(status_code=400, detail="Process ID is required")

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get process service
        processService = app.app_context.get_service(ProcessService)

        # Delete all files for the process from blob storage
        deleted_count = await processService.delete_all_files_from_blob(process_id)

        logger_service.log_info(
            f"Deleted {deleted_count} files from process {process_id}"
        )

        # Create result response with empty file list
        result_response = enlist_process_queue_response(
            message=f"All files deleted successfully. {deleted_count} files removed.",
            user_id=str(user_id),
            process_id=process_id,
            files=[],  # Empty list after deletion
        )

        # Add Header to process status url
        if response:
            response.headers["Location"] = f"/process/{process_id}/"

        return result_response

    except Exception as e:
        logger_service.log_error(f"Error in delete_process: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting process: {str(e)}")


@router.post(process_router_paths.START_PROCESSING, status_code=202)
async def start_processing(
    process_id: str = Form(..., description="Process ID with uploaded files"),
    request: Request = None,
    response: Response = None,
):
    """
    Start the migration processing workflow for a process with already uploaded files.
    This endpoint puts a message on the queue to begin processing the files uploaded via /upload.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info("Start Processing endpoint called")

        # Validate process_id is provided
        if not process_id:
            raise HTTPException(status_code=400, detail="Process ID is required")

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get process service
        processService = app.app_context.get_service(ProcessService)

        # Verify that files exist for this process (optional validation)
        # You could add a check here to ensure files were uploaded first

        # Create queue message for processing
        queue_message = enlist_process_queue_response(
            message="Processing started",
            user_id=str(user_id),
            process_id=process_id,
            files=[],  # Files are already uploaded, we don't need to include them in the queue message
        )

        # Enqueue the process for processing
        await processService.process_enqueue(queue_message=queue_message)

        logger_service.log_info(f"Processing started for process {process_id}")

        # Add Header to process status url
        if response:
            response.headers["Location"] = f"/process/{process_id}/"

        return {
            "message": "Processing started successfully",
            "process_id": process_id,
            "user_id": str(user_id),
            "status": "queued",
        }
    except Exception as e:
        logger_service.log_error(f"Error in start_processing: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error starting processing: {str(e)}"
        )


@router.get("/{process_id}/download")
async def download_process_files(
    process_id: str,
    request: Request,
):
    """
    Download all converted files and reports for a specific process as a ZIP file.
    Returns files from the {process_id}/converted folder in blob storage.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(
            f"Download endpoint called for process_id: {process_id}"
        )

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get process service
        processService = app.app_context.get_service(ProcessService)

        # Get all files from the converted folder
        converted_files = await processService.get_converted_files(process_id)

        if not converted_files:
            raise HTTPException(
                status_code=404, detail="No converted files found for this process"
            )

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_info in converted_files:
                # Add each file to the ZIP with its relative path
                zip_file.writestr(file_info.filename, file_info.content)

        zip_buffer.seek(0)

        logger_service.log_info(
            f"Created ZIP file with {len(converted_files)} files for process {process_id}"
        )

        # Return ZIP file as streaming response
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=process_{process_id}_converted.zip"
            },
        )

    except HTTPException as e:
        logger_service.log_error(f"HTTPException in download: {e.detail}")
        raise e
    except Exception as e:
        logger_service.log_error(f"Error in download_process_files: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error downloading files: {str(e)}"
        )


@router.get("/process-summary/{process_id}", response_model=ProcessSummaryResponse)
async def get_process_summary(
    process_id: str,
    request: Request,
):
    """
    Get process summary including process details and list of all migrated file names.
    Returns process information and list of converted files for the specified process.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(
            f"Process summary endpoint called for process_id: {process_id}"
        )

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get process service
        processService = app.app_context.get_service(ProcessService)

        # Get process summary (process entity and file names)
        process_entity, filenames = await processService.get_process_summary(process_id)

        # Create response
        response = ProcessSummaryResponse(
            Process=ProcessInfo(
                process_id=process_entity.id,
                created_at=process_entity.created_at,
                file_count=len(filenames),
            ),
            files=[ProcessSummaryFileInfo(filename=filename) for filename in filenames],
        )

        logger_service.log_info(
            f"Process summary retrieved for {process_id}: {len(filenames)} files"
        )

        return response

    except HTTPException as e:
        logger_service.log_error(f"HTTPException in process summary: {e.detail}")
        raise e
    except Exception as e:
        logger_service.log_error(f"Error in get_process_summary: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving process summary: {str(e)}"
        )


@router.get("/{process_id}/file/{filename}", response_model=FileContentResponse)
async def get_file_content(
    process_id: str,
    filename: str,
    request: Request,
):
    """
    Get the migrated content of a specific file for display.
    Returns the content of a file from the {process_id}/converted folder.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(
            f"File content endpoint called for process_id: {process_id}, filename: {filename}"
        )

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get process service
        processService = app.app_context.get_service(ProcessService)

        # Get the specific file content
        file_content = await processService.get_converted_file_content(
            process_id, filename
        )

        logger_service.log_info(
            f"File content retrieved for {filename} in process {process_id}"
        )

        return FileContentResponse(content=file_content)

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found for process '{process_id}'",
        )
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail=f"File '{filename}' is not a text file and cannot be displayed",
        )
    except HTTPException as e:
        logger_service.log_error(f"HTTPException in file content: {e.detail}")
        raise e
    except Exception as e:
        logger_service.log_error(f"Error in get_file_content: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving file content: {str(e)}"
        )


@router.post(process_router_paths.CANCEL_PROCESS, status_code=202)
async def cancel_process(
    process_id: str,
    request: Request,
    reason: Optional[str] = None,
):
    """
    Request cancellation of a running process.
    This endpoint forwards the kill request to the Processor's Control API.
    The processor will observe this request and terminate the running process.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(f"Cancel process request for process_id: {process_id}")

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get processor control URL from configuration
        config = app.app_context.configuration
        processor_url = config.processor_control_url or "http://processor:8080"
        processor_token = config.processor_control_token or ""

        # Prepare headers for processor control API
        headers = {}
        if processor_token:
            headers["Authorization"] = f"Bearer {processor_token}"

        # Forward kill request to Processor Control API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{processor_url}/processes/{process_id}/kill",
                json={"reason": reason or f"User {user_id} cancelled from UI"},
                headers=headers,
            )

            if response.status_code == 401:
                logger_service.log_error("Unauthorized access to processor control API")
                raise HTTPException(
                    status_code=502,
                    detail="Failed to authenticate with processor control API",
                )

            if response.status_code >= 400:
                logger_service.log_error(
                    f"Processor control API error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Processor control API error: {response.text}",
                )

            result = response.json()

        logger_service.log_info(
            f"Cancel request sent for process {process_id}, state: {result.get('kill_state', 'unknown')}"
        )

        return {
            "message": "Cancellation request submitted",
            "process_id": process_id,
            "kill_requested": result.get("kill_requested", True),
            "kill_state": result.get("kill_state", "pending"),
            "kill_requested_at": result.get("kill_requested_at", ""),
        }

    except httpx.TimeoutException:
        logger_service.log_error(f"Timeout connecting to processor control API")
        raise HTTPException(
            status_code=504,
            detail="Timeout connecting to processor control API",
        )
    except httpx.ConnectError:
        logger_service.log_error(f"Failed to connect to processor control API")
        raise HTTPException(
            status_code=503,
            detail="Processor control API is unavailable",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger_service.log_error(f"Error in cancel_process: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error cancelling process: {str(e)}"
        )


@router.get(process_router_paths.CANCEL_STATUS, status_code=200)
async def get_cancel_status(
    process_id: str,
    request: Request,
):
    """
    Get the cancellation status of a process.
    Returns the current kill state from the Processor's Control API.
    """
    app: TypedFastAPI = request.app
    logger_service: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        logger_service.log_info(f"Get cancel status for process_id: {process_id}")

        # Get authenticated user
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Get processor control URL from configuration
        config = app.app_context.configuration
        processor_url = config.processor_control_url or "http://processor:8080"
        processor_token = config.processor_control_token or ""

        # Prepare headers for processor control API
        headers = {}
        if processor_token:
            headers["Authorization"] = f"Bearer {processor_token}"

        # Get control status from Processor Control API
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{processor_url}/processes/{process_id}/control",
                headers=headers,
            )

            if response.status_code == 401:
                logger_service.log_error("Unauthorized access to processor control API")
                raise HTTPException(
                    status_code=502,
                    detail="Failed to authenticate with processor control API",
                )

            if response.status_code >= 400:
                logger_service.log_error(
                    f"Processor control API error: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Processor control API error: {response.text}",
                )

            result = response.json()

        return result

    except httpx.TimeoutException:
        logger_service.log_error(f"Timeout connecting to processor control API")
        raise HTTPException(
            status_code=504,
            detail="Timeout connecting to processor control API",
        )
    except httpx.ConnectError:
        logger_service.log_error(f"Failed to connect to processor control API")
        raise HTTPException(
            status_code=503,
            detail="Processor control API is unavailable",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger_service.log_error(f"Error in get_cancel_status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error getting cancel status: {str(e)}"
        )
