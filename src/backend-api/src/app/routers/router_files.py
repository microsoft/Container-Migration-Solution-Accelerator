import re
from uuid import uuid4

from fastapi import (
    APIRouter,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi import (
    File as FastAPIFile,
)
from fastapi.responses import Response
from libs.base.typed_fastapi import TypedFastAPI
from libs.models.entities import File, Process
from libs.sas.storage import AsyncStorageBlobHelper
from libs.services.auth import get_authenticated_user
from libs.services.input_validation import is_valid_uuid
from libs.services.interfaces import ILoggerService
from libs.sas.storage import AsyncStorageBlobHelper
from libs.models.entities import File, Process
from routers.models.files import FileUploadResult
from libs.repositories.process_repository import ProcessRepository
from libs.repositories.file_repository import FileRepository
from libs.repositories.process_repository import ProcessRepository

router = APIRouter(
    prefix="/api/file",
    tags=["file"],
    responses={404: {"description": "Not found"}},
)


@router.options("/upload")
async def upload_file_options():
    """Handle CORS preflight for upload endpoint"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
    )


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = FastAPIFile(...),  # Use FastAPI's File class
    process_id: str = Form(...),
):
    app: TypedFastAPI = request.app
    logger: ILoggerService = app.app_context.get_service(ILoggerService)

    try:
        authenticated_user = get_authenticated_user(request)
        user_id = authenticated_user.user_principal_id

        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        logger.log_info(f"process_id: {process_id}")
        if not is_valid_uuid(process_id):
            raise HTTPException(status_code=400, detail="Invalid process_id format")

        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        async with app.app_context.create_scope() as scope:
            processRepository = scope.get_service(ProcessRepository)
            fileRepository = scope.get_service(FileRepository)

            process_record = await processRepository.get_async(process_id)

            file_id = str(uuid4())
            file_name = re.sub(r"[^\w.-]", "_", file.filename)
            blob_path = f"{process_id}/source/{file_name}"
            file_content = await file.read()

            async with scope.get_service(AsyncStorageBlobHelper) as blobHelper:
                await blobHelper.upload_blob(
                    container_name=app.app_context.configuration.storage_account_process_container,
                    blob_name=blob_path,
                    data=file_content,
                    overwrite=True,
                )
                logger.log_info(
                    f"File {file_name} saved to Azure Blob Storage under process ID {process_id}."
                )

            file_record = File(
                id=file_id,
                process_id=process_id,
                name=file_name,
                blob_path=blob_path,
            )

            await fileRepository.add_async(file_record)
            logger.log_info(f"File {file_name} ({file_id}) record saved.")

            processFileCount = await fileRepository.count_async(
                {"process_id": process_id}
            )

            process_record.source_file_count = processFileCount
            if process_record.source_file_count > 0:
                process_record.status = "ready_to_process"

            await processRepository.update_async(process_record)
            logger.log_info(
                f"Process {process_id} source count updated to {process_record.source_file_count}."
            )

            return FileUploadResult(
                batch_id=process_record.id,
                file_id=file_record.id,
                file_name=file_record.name,
            )

    except HTTPException as e:
        logger.log_error(f"HTTPException: {e.detail}", e)
        raise e
    except Exception as e:
        logger.log_error(f"Exception: {str(e)}", e)
        raise HTTPException(status_code=500, detail="Internal server error") from e
