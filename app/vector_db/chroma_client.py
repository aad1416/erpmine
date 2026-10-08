import chromadb

from app.config.setting import settings


class ChromaClient:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChromaClient, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not ChromaClient._initialized:
            self.client = chromadb.PersistentClient(path=settings.vector_store_path)
            ChromaClient._initialized = True
