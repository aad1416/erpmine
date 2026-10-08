from fastapi import (
    APIRouter,
    Depends,
    status,
    HTTPException,
    Path as FastAPIPath,
    Query,
)
from typing import Annotated, List
from app.dependencies.auth import get_current_user
from app.dependencies.documents import get_document_service
from app.services.documents import DocumentService
from app.schemas.documents import (
    DocumentCreateRequest,
    DocumentResponse,
    DocumentWithFileResponse,
    DocumentMetadataUpdateRequest,
)
from app.db.models import User

documents_router = APIRouter()


@documents_router.post(
    "/admin/features/{feature_id}/documents/process",
    response_model=List[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def process_documents(
    feature_id: Annotated[int, FastAPIPath(..., description="The ID of the feature")],
    request: DocumentCreateRequest,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    get_current_user: Annotated[User, Depends(get_current_user)],
):
    if get_current_user.user_type != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )

    if not request.file_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No file IDs provided"
        )

    created_documents = await document_service.add_documents(
        file_ids=request.file_ids, metadata=request.metadata, feature_id=feature_id
    )
    return created_documents


@documents_router.get(
    "/admin/features/{feature_id}/documents",
    response_model=List[DocumentWithFileResponse],
    status_code=status.HTTP_200_OK,
)
async def get_all_documents_for_feature(
    feature_id: Annotated[int, FastAPIPath(..., description="The ID of the feature")],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
):
    """
    Get all documents for a specific feature with file details.

    Returns list of documents with associated file information including:
    - File name, size, mime type, extension
    - File upload timestamp
    - File metadata
    """
    documents = document_service.get_documents(feature_id)
    return [DocumentWithFileResponse.model_validate(doc) for doc in documents]


@documents_router.get(
    "/admin/features/{feature_id}/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_document_by_id(
    document_id: Annotated[str, FastAPIPath(..., description="The ID of the document")],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
):
    document = document_service.get_document(document_id)
    return document


@documents_router.delete(
    "/admin/features/{feature_id}/documents",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_documents(
    feature_id: Annotated[int, FastAPIPath(..., description="The ID of the feature")],
    document_ids: Annotated[
        List[str],
        Query(..., description="List of document IDs to delete"),
    ],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
):
    """
    Delete one or more documents.

    Accepts multiple document IDs via query parameter: ?document_ids=id1&document_ids=id2
    """
    if not document_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one document ID is required",
        )
    document_service.delete_documents(document_ids=document_ids)
    return


@documents_router.put(
    "/admin/features/{feature_id}/documents/{document_id}/metadata",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
async def update_document_metadata_route(
    document_id: Annotated[
        str, FastAPIPath(..., description="The ID of the document to update")
    ],
    request: DocumentMetadataUpdateRequest,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
):
    updated_document = document_service.update_document_metadata(
        document_id=document_id, new_metadata=request.metadata
    )
    return updated_document
