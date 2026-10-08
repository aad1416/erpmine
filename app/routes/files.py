from fastapi import (
    APIRouter,
    Depends,
    UploadFile,
    File as FastAPIFile,
    HTTPException,
    status,
    Query,
)
from fastapi.responses import FileResponse as FastAPIFileResponse
from typing import Annotated, List
from pathlib import Path
from app.dependencies.auth import get_current_user
from app.dependencies.files import get_files_service
from app.dependencies.database import get_db
from app.services.files import FilesService
from app.schemas.files import FileResponse
from app.db.models import User
from app.config.setting import settings
from sqlalchemy.orm import Session

files_router = APIRouter()


@files_router.post(
    "/files/upload",
    response_model=List[FileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_files(
    upload_files: Annotated[
        List[UploadFile], FastAPIFile(description="Files to upload")
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    files_service: Annotated[FilesService, Depends(get_files_service)],
):
    """
    Upload one or more files.

    Accepts multiple files via multipart/form-data. Each file is validated
    for type and size before upload. Returns a list of uploaded file details.
    """
    if not upload_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    allowed_types = [t.strip().lower() for t in settings.allowed_file_types if t.strip()]
    allowed_extensions = {t.lstrip(".") for t in allowed_types if "/" not in t}
    allowed_mime_types = {t for t in allowed_types if "/" in t}
    max_file_size = settings.max_file_size_mb * 1024 * 1024  # Convert MB to bytes
    uploaded_files = []
    errors = []

    for idx, upload_file in enumerate(upload_files):
        # Validate filename
        if not upload_file.filename:
            errors.append(f"File {idx + 1}: No filename provided")
            continue

        extension = Path(upload_file.filename).suffix.lower().lstrip(".")
        content_type = (upload_file.content_type or "").lower()

        # File type validation
        if extension not in allowed_extensions and content_type not in allowed_mime_types:
            allowed_display = ", ".join(allowed_types)
            errors.append(
                f"File '{upload_file.filename}': Unsupported file type: {content_type or extension}. "
                f"Allowed types are: {allowed_display}"
            )
            continue

        # File size validation
        file_content = await upload_file.read()
        if len(file_content) > max_file_size:
            errors.append(
                f"File '{upload_file.filename}': File size exceeds limit of {settings.max_file_size_mb}MB"
            )
            continue
        upload_file.file.seek(0)  # Reset file pointer after reading content

        # Upload file
        try:
            file = files_service.create(upload_file, current_user.id)
            uploaded_files.append(FileResponse.model_validate(file))
        except Exception as e:
            errors.append(f"File '{upload_file.filename}': {str(e)}")

    # If no files were successfully uploaded, raise an error
    if not uploaded_files:
        error_message = "Failed to upload any files. "
        if errors:
            error_message += "Errors: " + "; ".join(errors)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # If some files failed but at least one succeeded, return success with warnings
    # (FastAPI will return 201, but the client can check the response)
    return uploaded_files


@files_router.get("/files", response_model=List[FileResponse], tags=["files"])
def list_files(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    """
    List all files uploaded by the current user.

    Returns list of files with their IDs, names, paths, and metadata.
    """
    from app.repositories.files import FilesRepository
    from app.db.models import File

    try:
        # Get all files for current user
        files = db.query(File).filter(File.user_id == current_user.id).all()
        return [FileResponse.model_validate(file) for file in files]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve files: {str(e)}",
        )


@files_router.get("/files/{file_id}", response_model=FileResponse, tags=["files"])
def get_file(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    files_service: Annotated[FilesService, Depends(get_files_service)],
):
    """
    Get details of a specific file.

    Returns file metadata including ID, name, path, size, etc.
    """
    file = files_service.get(file_id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found",
        )

    # Verify file belongs to user
    if file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this file",
        )

    return FileResponse.model_validate(file)


@files_router.get("/files/{file_id}/download", tags=["files"])
def download_file(
    file_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    files_service: Annotated[FilesService, Depends(get_files_service)],
):
    """
    Download a specific file.

    Returns the file as a downloadable attachment.
    """
    from pathlib import Path

    file = files_service.get(file_id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with id {file_id} not found",
        )

    # Verify file belongs to user
    if file.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this file",
        )

    # Check if file exists on disk
    file_path = Path(file.path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
        )

    # Return file as downloadable response
    return FastAPIFileResponse(
        path=str(file_path),
        filename=file.file_name,
        media_type=file.mime_type or "application/octet-stream",
    )


@files_router.delete("/files", status_code=status.HTTP_204_NO_CONTENT, tags=["files"])
def delete_files(
    file_ids: Annotated[
        List[str],
        Query(..., description="List of file IDs to delete"),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    files_service: Annotated[FilesService, Depends(get_files_service)],
    db: Session = Depends(get_db),
):
    """
    Delete one or more files.

    Accepts multiple file IDs via query parameter: ?file_ids=id1&file_ids=id2
    Deletes both the physical files from disk and the database records.
    Cannot delete a file that has an associated document. Delete the document first.
    """
    from app.db.models import Document

    if not file_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file ID is required",
        )

    # Remove duplicates while preserving order
    unique_file_ids = list(dict.fromkeys(file_ids))

    errors = []
    successfully_deleted = []
    files_to_delete = []

    # Validate all files first
    for file_id in unique_file_ids:
        file = files_service.get(file_id)

        if not file:
            errors.append(f"{file_id}: File not found")
            continue

        # Verify file belongs to user
        if file.user_id != current_user.id:
            errors.append(f"{file_id}: You don't have permission to delete this file")
            continue

        # Check if file has an associated document
        associated_document = (
            db.query(Document).filter(Document.file_id == file_id).first()
        )
        if associated_document:
            errors.append(
                f"{file_id}: Cannot delete file. It has an associated document (ID: {associated_document.id}). Please delete the document first."
            )
            continue

        files_to_delete.append(file_id)

    # If all files failed validation, return error
    if not files_to_delete:
        error_message = "Failed to delete any files. "
        if errors:
            error_message += "Errors: " + "; ".join(errors)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Delete all valid files
    for file_id in files_to_delete:
        try:
            files_service.delete(file_id)
            successfully_deleted.append(file_id)
        except Exception as e:
            errors.append(f"{file_id}: Failed to delete - {str(e)}")

    # If some files failed to delete, raise an error with details
    if errors:
        success_msg = (
            f"Successfully deleted {len(successfully_deleted)} file(s). "
            if successfully_deleted
            else ""
        )
        error_message = success_msg + "Errors: " + "; ".join(errors)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message,
        )
