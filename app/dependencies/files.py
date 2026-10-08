from app.repositories.files import FilesRepository
from app.services.files import FilesService
from app.dependencies.database import get_db
from app.config.setting import settings
from app.config.setting import Settings
from sqlalchemy.orm import Session
from fastapi import Depends
from typing import Annotated


def get_files_repository(db: Annotated[Session, Depends(get_db)]) -> FilesRepository:
    return FilesRepository(db)


def get_files_service(
    files_repository: Annotated[FilesRepository, Depends(get_files_repository)],
) -> FilesService:
    return FilesService(files_repository)
