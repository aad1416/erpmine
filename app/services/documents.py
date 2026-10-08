from typing import List, Dict, Optional
from chromadb import Collection
from app.db.models import Document
from app.repositories import DocumentRepository
from app.services.files import FilesService
from app.services.embedding_service import EmbeddingService
from app.utils.document_parser import DocumentParser
from app.utils.markdown_chunker import MarkdownChunker
from fastapi import HTTPException
import uuid
import os
from datetime import datetime
import time
from app.utils.eval_logger import eval_logger

RESERVED_KEYS = frozenset(
    {
        "document_id",
        "file_id",
        "feature_id",
        "filename",
        "file_type",
        "chunk_type",
        "chunk_index",
        "table_id",
        "table_html",
        "table_truncated",
        "row_range",
        "row_start",
        "row_end",
        "section_path",
        "page",
        "page_label",
        "active",
    }
)


class DocumentService:
    def __init__(
        self,
        files_service: FilesService,
        collection: Collection,
        document_repository: DocumentRepository,
        parser_service: DocumentParser,
        chunker: MarkdownChunker,
        embedding_service: EmbeddingService,
    ):
        self.files_service = files_service
        self.collection = collection
        self.document_repository = document_repository
        self.parser_service = parser_service
        self.chunker = chunker
        self.embedding_service = embedding_service

    def _get_document_active_status(self, document_id: str) -> Optional[bool]:
        try:
            results = self.collection.get(
                where={"document_id": document_id},
                limit=1,
                include=["metadatas"],
            )
            if results["ids"] and results["metadatas"] and results["metadatas"][0]:
                return results["metadatas"][0].get("active") == "true"
        except Exception:
            pass
        return None

    def _enrich_document_active_status(self, document) -> None:
        active = self._get_document_active_status(document.id)
        document.active = active

    def get_documents(self, feature_id: int):
        """
        Get all documents for a specific feature.

        Args:
            feature_id: The ID of the feature to get documents for

        Returns:
            List of Document objects (empty list if no documents found)

        Raises:
            HTTPException: If feature_id is invalid or database query fails
        """
        if not isinstance(feature_id, int) or feature_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="Invalid feature_id. Must be a positive integer.",
            )

        try:
            documents = self.document_repository.get_all_by_feature_id(feature_id)
            if not documents:
                return []
            for doc in documents:
                self._enrich_document_active_status(doc)
            return documents
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve documents for feature {feature_id}: {str(e)}",
            )

    def get_document(self, document_id: str):
        document = self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        self._enrich_document_active_status(document)
        return document

    async def add_documents(
        self,
        file_ids: List[str],
        feature_id: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> List[Document]:
        """
        Add multiple documents to the system at once.

        Args:
            file_ids: List of file IDs to process into documents

        Returns:
            List of created Document objects

        Raises:
            HTTPException: If any file is not found or processing fails
        """
        if not file_ids:
            raise HTTPException(status_code=400, detail="No file IDs provided")

        safe_metadata = (
            self._sanitize_user_metadata(metadata) if metadata is not None else None
        )
        created_documents = []
        all_documents = []
        all_metadatas = []
        all_ids = []
        failed_files = []

        # Process each file
        for file_id in file_ids:
            file = self.files_service.get(file_id)
            if not file:
                failed_files.append(f"{file_id}: File not found in database")
                continue

            # Check if file exists on disk
            if not os.path.exists(file.path):
                failed_files.append(
                    f"{file_id}: File does not exist on disk (path: {file.path})"
                )
                continue

            document_id = str(uuid.uuid4())
            document = Document(
                id=document_id,
                feature_id=feature_id,
                file_id=file_id,
                document_metadata=safe_metadata,
            )

            try:
                start_time = time.time()
                chunks = await self._parse_and_chunk_file(
                    file=file,
                    document_id=document_id,
                    feature_id=feature_id,
                    metadata=safe_metadata,
                )
                end_time = time.time()
                
                if not chunks:
                    failed_files.append(f"{file_id}: No content extracted from file")
                    eval_logger.log_document_process(file.id, file.file_name, 0.0, 0, "No content extracted")
                    continue

                # Log successful parsing execution
                eval_logger.log_document_process(
                    file_id=file.id,
                    file_name=file.file_name,
                    duration_seconds=end_time - start_time,
                    chunks_generated=len(chunks)
                )

                # Generate unique IDs for each chunk
                chunk_ids = [str(uuid.uuid4()) for _ in range(len(chunks))]

                # Add to batch lists
                all_documents.extend([chunk.text for chunk in chunks])
                all_metadatas.extend([chunk.metadata for chunk in chunks])
                all_ids.extend(chunk_ids)
                created_documents.append(document)
            except Exception as e:
                failed_files.append(f"{file_id}: Failed to parse file - {str(e)}")
                eval_logger.log_document_process(file.id, file.file_name, 0.0, 0, str(e))
                continue

        if failed_files:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to process some files: {', '.join(failed_files)}",
            )

        if not created_documents:
            raise HTTPException(
                status_code=400, detail="No documents were successfully processed"
            )

        # Add all pages to collection in one batch
        if all_documents:
            try:
                embeddings = self.embedding_service.embed_texts(all_documents)
                if len(embeddings) != len(all_documents):
                    raise ValueError(
                        "Embedding count does not match documents count."
                    )
                embedding_dim = len(embeddings[0]) if embeddings and embeddings[0] else 0
                self._ensure_collection_embedding_metadata(embedding_dim)
                self.collection.add(
                    ids=all_ids,
                    documents=all_documents,
                    metadatas=all_metadatas,
                    embeddings=embeddings,
                )
            except Exception as e:
                # Clean up any created documents from database if vector store fails
                for doc in created_documents:
                    try:
                        self.document_repository.delete(doc.id)
                    except Exception:
                        pass
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to add documents to vector store: {str(e)}",
                )

        # Create all document records
        created_records = []
        failed_creates = []
        for document in created_documents:
            try:
                created_record = self.document_repository.create(document)
                created_records.append(created_record)
            except Exception as e:
                failed_creates.append(f"{document.id}: {str(e)}")
                # Clean up vector store entries for failed database creates
                try:
                    results = self.collection.get(where={"document_id": document.id})
                    if results["ids"]:
                        self.collection.delete(ids=results["ids"])
                except Exception:
                    pass

        if failed_creates:
            # Clean up successfully created database records if some failed
            for record in created_records:
                try:
                    self.document_repository.delete(record.id)
                    results = self.collection.get(where={"document_id": record.id})
                    if results["ids"]:
                        self.collection.delete(ids=results["ids"])
                except Exception:
                    pass
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create some document records: {', '.join(failed_creates)}",
            )

        return created_records

    async def _parse_and_chunk_file(
        self,
        file,
        document_id: str,
        feature_id: int,
        metadata: Optional[Dict[str, str]],
    ):
        file_type = self._resolve_file_type(file)
        markdown = await self.parser_service.parse_file_async(file.path, file_type)

        base_metadata = self._build_base_metadata(
            file=file,
            document_id=document_id,
            feature_id=feature_id,
            metadata=metadata,
            file_type=file_type,
        )
        chunks = self.chunker.chunk_markdown(markdown, base_metadata)
        for idx, chunk in enumerate(chunks, start=1):
            chunk.metadata["chunk_index"] = str(idx)
        return chunks

    def _sanitize_user_metadata(
        self, user_metadata: Optional[Dict[str, str]]
    ) -> Dict[str, str]:
        return {
            key: value
            for key, value in (user_metadata or {}).items()
            if key not in RESERVED_KEYS
        }

    def _build_base_metadata(
        self,
        file,
        document_id: str,
        feature_id: Optional[int],
        metadata: Optional[Dict[str, str]],
        file_type: str,
    ) -> Dict[str, str]:
        safe_user_metadata = self._sanitize_user_metadata(metadata)
        base_metadata: Dict[str, str] = {
            "document_id": document_id,
            "file_id": file.id,
            "filename": file.file_name,
            "file_type": file_type,
            "active": "true",
        }
        if feature_id is not None:
            base_metadata["feature_id"] = str(feature_id)
        merged_metadata = {**safe_user_metadata, **base_metadata}
        return self._stringify_metadata(merged_metadata)

    def _resolve_file_type(self, file) -> str:
        if file.extension:
            return file.extension.lower().lstrip(".")
        if file.file_name:
            _, ext = os.path.splitext(file.file_name)
            if ext:
                return ext.lower().lstrip(".")
        if file.mime_type and "/" in file.mime_type:
            return file.mime_type.split("/")[-1].lower()
        return "unknown"

    def _stringify_metadata(self, metadata: Dict[str, str]) -> Dict[str, str]:
        return {key: str(value) for key, value in metadata.items() if value is not None}

    def _ensure_collection_embedding_metadata(self, embedding_dim: int) -> None:
        if embedding_dim <= 0:
            raise HTTPException(
                status_code=500,
                detail="Invalid embedding dimension for collection",
            )

        expected = self.embedding_service.get_embedding_signature()
        expected["embedding_dim"] = str(embedding_dim)

        existing = getattr(self.collection, "metadata", None)
        if not isinstance(existing, dict):
            existing = {}

        mismatches = []
        for key, expected_value in expected.items():
            existing_value = existing.get(key)
            if existing_value is None:
                continue
            if str(existing_value) != str(expected_value):
                mismatches.append(f"{key}={existing_value} expected={expected_value}")

        if mismatches:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Embedding configuration mismatch. Reindex the collection. "
                    + "; ".join(mismatches)
                ),
            )

        if any(key not in existing for key in expected):
            if hasattr(self.collection, "modify"):
                try:
                    self.collection.modify(metadata={**existing, **expected})
                except Exception:
                    pass

    def _set_document_active(self, document_id: str, active: bool) -> None:
        active_value = "true" if active else "false"
        results = self.collection.get(
            where={"document_id": document_id},
            include=["metadatas"],
        )
        if not results["ids"]:
            raise HTTPException(
                status_code=404,
                detail=f"No chunks found for document {document_id} in vector store",
            )

        updated_metadatas = []
        for meta in results["metadatas"]:
            updated = {**(meta or {}), "active": active_value}
            updated_metadatas.append(updated)

        self.collection.update(ids=results["ids"], metadatas=updated_metadatas)

    def activate_document(self, document_id: str) -> None:
        document = self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        self._set_document_active(document_id, True)

    def deactivate_document(self, document_id: str) -> None:
        document = self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        self._set_document_active(document_id, False)

    def delete_documents(self, document_ids: List[str]) -> None:
        """
        Delete multiple documents from the system at once.

        Args:
            document_ids: List of document IDs to delete

        Raises:
            HTTPException: If any document is not found or deletion fails
        """
        if not document_ids:
            raise HTTPException(status_code=400, detail="No document IDs provided")

        # Check which documents exist
        existing_documents = []
        missing_ids = []
        for document_id in document_ids:
            document = self.document_repository.get_by_id(document_id)
            if document:
                existing_documents.append(document_id)
            else:
                missing_ids.append(document_id)

        if missing_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Documents not found: {', '.join(missing_ids)}",
            )

        # Delete from database
        failed_deletes = []
        successfully_deleted = []
        for document_id in existing_documents:
            try:
                self.document_repository.delete(document_id)
                successfully_deleted.append(document_id)
            except Exception as e:
                failed_deletes.append(f"{document_id}: {str(e)}")

        if failed_deletes:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete some documents from database: {', '.join(failed_deletes)}",
            )

        # Collect all chunk IDs to delete from vector store
        all_chunk_ids = []
        for document_id in successfully_deleted:
            try:
                results = self.collection.get(where={"document_id": document_id})
                if results["ids"]:
                    all_chunk_ids.extend(results["ids"])
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to query vector store for document {document_id}: {str(e)}",
                )

        # Delete all chunks in one batch
        if all_chunk_ids:
            try:
                self.collection.delete(ids=all_chunk_ids)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete document chunks from vector store: {str(e)}",
                )

    def update_document_metadata(
        self,
        document_id: str,
        new_metadata: Dict[str, str],
    ) -> Document:
        document = self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        try:
            # Fetch all chunks associated with the document
            results = self.collection.get(where={"document_id": document_id})
            if not results["ids"]:
                raise HTTPException(
                    status_code=404,
                    detail="No chunks found for document in vector store",
                )

            # Update metadata for each chunk
            safe_meta = self._sanitize_user_metadata(new_metadata)
            updated_ids = []
            updated_metadatas = []
            for i, chunk_id in enumerate(results["ids"]):
                current_metadata = (
                    results["metadatas"][i] if results["metadatas"] else {}
                )
                # Merge new metadata, ensuring all values are strings for ChromaDB
                merged_metadata = self._stringify_metadata(
                    {**current_metadata, **safe_meta}
                )
                updated_ids.append(chunk_id)
                updated_metadatas.append(merged_metadata)

            if updated_ids:
                self.collection.update(ids=updated_ids, metadatas=updated_metadatas)

            # Update the document record in the relational database if necessary
            # For now, document.metadata is not used in the relational DB, but if it were,
            # this is where it would be updated.
            document.document_metadata = safe_meta
            updated_document = self.document_repository.update(document)

            return updated_document

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update document metadata in vector store: {str(e)}",
            )

    async def reprocess_document(self, document_id: str) -> Document:
        document = self.document_repository.get_by_id(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        file = self.files_service.get(document.file_id)
        if not file:
            raise HTTPException(
                status_code=404,
                detail=f"Associated file {document.file_id} not found for document {document_id}",
            )

        # 1. Read active status and delete existing chunks from ChromaDB
        previous_active = "true"
        try:
            results = self.collection.get(where={"document_id": document_id})
            if results["ids"]:
                if results["metadatas"] and results["metadatas"][0]:
                    previous_active = results["metadatas"][0].get("active", "true")
                self.collection.delete(ids=results["ids"])
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete old chunks from vector store for document {document_id}: {str(e)}",
            )

        # 2. Parse, chunk, and embed the document again
        try:
            start_time = time.time()
            chunks = await self._parse_and_chunk_file(
                file=file,
                document_id=document.id,
                feature_id=document.feature_id,
                metadata=document.document_metadata or {},
            )
            end_time = time.time()

            if chunks:
                eval_logger.log_document_process(
                    file_id=file.id,
                    file_name=file.file_name,
                    duration_seconds=end_time - start_time,
                    chunks_generated=len(chunks)
                )

                for chunk in chunks:
                    chunk.metadata["active"] = previous_active

                ids = [str(uuid.uuid4()) for _ in range(len(chunks))]
                documents = [chunk.text for chunk in chunks]
                embeddings = self.embedding_service.embed_texts(documents)
                if len(embeddings) != len(documents):
                    raise ValueError(
                        "Embedding count does not match documents count."
                    )
                embedding_dim = len(embeddings[0]) if embeddings and embeddings[0] else 0
                self._ensure_collection_embedding_metadata(embedding_dim)
                self.collection.add(
                    ids=ids,
                    documents=documents,
                    metadatas=[chunk.metadata for chunk in chunks],
                    embeddings=embeddings,
                )

            # Update the document's updated_at timestamp in the relational DB
            document.updated_at = datetime.now(datetime.UTC)
            updated_document = self.document_repository.update(document)

            return updated_document
        except Exception as e:
            # If reprocessing fails, attempt to re-add the old chunks if possible, or log a critical error.
            # For now, we'll just raise the exception.
            raise HTTPException(
                status_code=500,
                detail=f"Failed to reprocess document {document_id}: {str(e)}",
            )
