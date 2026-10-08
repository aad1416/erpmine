import os
import uuid
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from fastapi import UploadFile
from app.db.models import File
from app.repositories import FilesRepository
from app.config.setting import settings


class FilesService:
    def __init__(self, files_repository: FilesRepository):
        self.files_repository = files_repository
        self.uploads_path = settings.file_storage_path

    def create(self, upload_file: UploadFile, user_id: str = None) -> File:
        # Generate unique id for file path
        unique_id = str(uuid.uuid4())

        # Extract file metadata
        file_name = upload_file.filename
        extension = Path(file_name).suffix.lstrip(".") if file_name else None

        # Read file content
        content = upload_file.file.read()
        file_size = len(content)
        mime_type = upload_file.content_type

        # Create storage directory if it doesn't exist
        storage_path = Path(self.uploads_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        # Generate file path using unique_id
        if extension:
            file_path = storage_path / f"{unique_id}.{extension}"
        else:
            file_path = storage_path / unique_id

        # Write file to disk
        with open(file_path, "wb") as f:
            f.write(content)

        # Create File model instance
        now = datetime.now(timezone.utc)
        file_model = File(
            id=unique_id,
            file_name=file_name,
            path=str(file_path),
            extension=extension,
            size=file_size,
            mime_type=mime_type,
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )

        # Save to repository
        return self.files_repository.create(file_model)

    def create_from_bytes(
        self,
        content: bytes,
        file_name: str,
        mime_type: Optional[str] = None,
        user_id: str = None,
    ) -> File:
        """Bytes-accepting counterpart to `create()` — for content generated
        in-process (e.g. `export_excel`) rather than uploaded by a client."""
        unique_id = str(uuid.uuid4())
        extension = Path(file_name).suffix.lstrip(".") if file_name else None

        storage_path = Path(self.uploads_path)
        storage_path.mkdir(parents=True, exist_ok=True)

        if extension:
            file_path = storage_path / f"{unique_id}.{extension}"
        else:
            file_path = storage_path / unique_id

        with open(file_path, "wb") as f:
            f.write(content)

        now = datetime.now(timezone.utc)
        file_model = File(
            id=unique_id,
            file_name=file_name,
            path=str(file_path),
            extension=extension,
            size=len(content),
            mime_type=mime_type,
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )

        return self.files_repository.create(file_model)

    def get(self, file_id: str) -> Optional[File]:
        return self.files_repository.get_by_id(file_id)

    def delete(self, file_id: str) -> None:
        # Get file from repository
        file_model = self.files_repository.get_by_id(file_id)

        if not file_model:
            return

        # Delete physical file from disk
        file_path = Path(file_model.path)
        if file_path.exists():
            file_path.unlink()

        # Delete database record
        self.files_repository.delete(file_id)
