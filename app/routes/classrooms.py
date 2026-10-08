from fastapi import (
    APIRouter,
    Depends,
    status,
    HTTPException,
    Path as FastAPIPath,
)
from fastapi.responses import FileResponse
from typing import Annotated, List

from app.dependencies.auth import get_admin_user
from app.dependencies.classrooms import get_classroom_service
from app.services.classroom_service import ClassroomService
from app.schemas.classrooms import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomResponse,
    ClassroomItemsCreateRequest,
    ClassroomItemsDeleteRequest,
    ClassroomItemsWithDocumentsCreateRequest,
    ClassroomItemDocumentUploadRequest,
    ClassroomItemDocumentResponse,
    ClassroomItemResponse,
    DocumentActivationRequest,
)
from app.db.models import User

classrooms_router = APIRouter(tags=["classrooms"])


@classrooms_router.get(
    "/admin/classrooms",
    response_model=List[ClassroomResponse],
)
async def list_classrooms(
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    return classroom_service.list_classrooms()


@classrooms_router.post(
    "/admin/classrooms",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_classroom(
    request: ClassroomCreate,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    return classroom_service.create_classroom(name=request.name)


@classrooms_router.patch(
    "/admin/classrooms/{classroom_id}",
    response_model=ClassroomResponse,
)
async def rename_classroom(
    classroom_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom")
    ],
    request: ClassroomUpdate,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    return classroom_service.rename_classroom(
        classroom_id=classroom_id, name=request.name
    )


@classrooms_router.delete(
    "/admin/classrooms/{classroom_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_classroom(
    classroom_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    classroom_service.delete_classroom(classroom_id=classroom_id)


@classrooms_router.get(
    "/admin/classrooms/{classroom_id}/items",
    response_model=List[ClassroomItemResponse],
)
async def list_classroom_items(
    classroom_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    return classroom_service.list_classroom_items(classroom_id=classroom_id)


@classrooms_router.post(
    "/admin/classrooms/{classroom_id}/items/{item_id}",
    response_model=ClassroomItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def assign_item_to_classroom(
    classroom_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom")
    ],
    item_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom item")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    classroom_service.assign_item_to_classroom(
        classroom_id=classroom_id, item_id=item_id
    )
    # Return the item itself for convenience; assignment is a side-effect.
    item = classroom_service.item_repo.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Classroom item not found")
    return item


@classrooms_router.delete(
    "/admin/classrooms/{classroom_id}/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unassign_item_from_classroom(
    classroom_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom")
    ],
    item_id: Annotated[
        str, FastAPIPath(..., description="The ID of the classroom item")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    classroom_service.unassign_item_from_classroom(
        classroom_id=classroom_id, item_id=item_id
    )


@classrooms_router.get(
    "/admin/classroom-items",
    response_model=List[ClassroomItemResponse],
)
async def list_items(
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    return classroom_service.list_items()


@classrooms_router.post(
    "/admin/classroom-items",
    response_model=List[ClassroomItemResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_items(
    request: ClassroomItemsCreateRequest,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    items = [entry.model_dump() for entry in request.items]
    return classroom_service.create_items(items=items)


@classrooms_router.delete(
    "/admin/classroom-items",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_items(
    request: ClassroomItemsDeleteRequest,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    items = [entry.model_dump() for entry in request.items]
    classroom_service.delete_items(items=items)


@classrooms_router.post(
    "/admin/classroom-items/with-documents",
    response_model=List[ClassroomItemDocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_items_with_documents(
    request: ClassroomItemsWithDocumentsCreateRequest,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    items = [entry.model_dump() for entry in request.items]
    return await classroom_service.create_items_with_documents(items=items)


@classrooms_router.get(
    "/admin/classroom-items/{inventory_item_id}/documents",
    response_model=List[ClassroomItemDocumentResponse],
)
async def list_item_documents(
    inventory_item_id: Annotated[
        str, FastAPIPath(..., description="The inventory item ID")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    return classroom_service.list_item_documents(inventory_item_id=inventory_item_id)


@classrooms_router.post(
    "/admin/classroom-items/{inventory_item_id}/documents",
    response_model=ClassroomItemDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    inventory_item_id: Annotated[
        str, FastAPIPath(..., description="The inventory item ID")
    ],
    request: ClassroomItemDocumentUploadRequest,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    item_doc = await classroom_service.upload_document(
        inventory_item_id=inventory_item_id,
        file_id=request.file_id,
        inventory_item_document_id=request.inventory_item_document_id,
    )
    return item_doc


@classrooms_router.patch(
    "/admin/classroom-documents/{inventory_item_document_id}/activation",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def toggle_document_activation(
    inventory_item_document_id: Annotated[
        str, FastAPIPath(..., description="The inventory item document ID")
    ],
    request: DocumentActivationRequest,
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    classroom_service.toggle_document_activation(
        inventory_item_document_id=inventory_item_document_id,
        active=request.active,
    )


@classrooms_router.delete(
    "/admin/classroom-documents/{inventory_item_document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_document(
    inventory_item_document_id: Annotated[
        str, FastAPIPath(..., description="The inventory item document ID")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    classroom_service.delete_document(
        inventory_item_document_id=inventory_item_document_id,
    )


@classrooms_router.get(
    "/admin/classroom-documents/{inventory_item_document_id}/download",
)
async def download_document(
    inventory_item_document_id: Annotated[
        str, FastAPIPath(..., description="The inventory item document ID")
    ],
    classroom_service: Annotated[ClassroomService, Depends(get_classroom_service)],
    current_user: Annotated[User, Depends(get_admin_user)],
):
    file_info = classroom_service.download_document(
        inventory_item_document_id=inventory_item_document_id,
    )
    return FileResponse(
        path=file_info["path"],
        filename=file_info["filename"],
        media_type=file_info["mime_type"],
    )
