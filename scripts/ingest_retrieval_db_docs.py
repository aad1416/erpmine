import os
import uuid
import asyncio
from typing import List, Optional
from pathlib import Path

# Add project root to path so we can import app
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config.setting import settings
from app.dependencies.vector_store import get_chroma_client
from app.dependencies.embeddings import get_embedding_service

async def ingest_retrieval_db_docs(docs_dir: str = "docs/database/retrieval-docs"):
    """
    Ingests specialized retrieval documentation markdown files into ChromaDB.
    These docs are optimized for search/discovery.
    """
    client = get_chroma_client()
    embedding_service = get_embedding_service()
    
    collection_name = "database_retrieval_docs"
    print(f"Targeting retrieval collection: {collection_name}")
    
    # Ensure collection exists
    collection = client.client.get_or_create_collection(
        name=collection_name, 
        metadata={"hnsw:space": settings.VECTOR_STORE_DISTANCE_SPACE}
    )
    
    docs_path = Path(docs_dir)
    if not docs_path.exists():
        print(f"Error: Directory {docs_dir} not found.")
        return

    files = list(docs_path.glob("*.md"))
    print(f"Found {len(files)} retrieval documentation files in {docs_dir}")

    documents = []
    metadatas = []
    ids = []

    for file_path in files:
        table_name = file_path.stem
        # Skip hidden or non-table files if any
        if table_name.startswith('.'):
            continue
            
        content = file_path.read_text(encoding="utf-8")
        
        # Each table doc is ingested as a single high-quality chunk
        documents.append(content)
        metadatas.append({
            "table_name": table_name,
            "filename": file_path.name,
            "chunk_type": "retrieval_doc",
            "active": "true" 
        })
        ids.append(table_name) # Deterministic ID to prevent duplicates

    if documents:
        print(f"Generating embeddings for {len(documents)} tables...")
        embeddings = embedding_service.embed_texts(documents)
        
        print(f"Adding to ChromaDB...")
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        print(f"SUCCESS: Ingested {len(documents)} retrieval docs into '{collection_name}'.")
    else:
        print("No documents found to ingest.")

if __name__ == "__main__":
    try:
        asyncio.run(ingest_retrieval_db_docs())
    except Exception as e:
        print(f"Ingestion failed: {e}")
        sys.exit(1)
