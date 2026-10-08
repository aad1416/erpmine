from typing import Dict, Iterable, List, Optional

from app.config.setting import settings


class EmbeddingService:
    """
    Embedding Service

    Responsibilities:
    - Initialize embedding provider based on settings
    - Provide batch embedding for document chunks
    - Support multiple providers (OpenAI, Chroma default)
    """

    def __init__(
        self,
        provider: str,
        model_name: Optional[str],
        batch_size: int,
        openai_api_key: Optional[str],
    ):
        if not provider or not str(provider).strip():
            raise ValueError("EMBEDDING_PROVIDER is required")
        self.provider = str(provider).strip().lower()
        self.model_name = model_name
        self.batch_size = max(1, batch_size)
        self.openai_api_key = openai_api_key
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            self._embedder = self._init_embedder()
        return self._embedder

    def _init_embedder(self):
        if self.provider == "openai":
            try:
                from langchain_openai import OpenAIEmbeddings
            except ImportError as exc:
                raise ImportError(
                    "langchain-openai is not installed. "
                    "Please install it with: pip install langchain-openai"
                ) from exc

            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY not found in settings")

            model_name = self.model_name or "text-embedding-3-small"
            return OpenAIEmbeddings(
                model=model_name,
                api_key=self.openai_api_key,
            )

        if self.provider in {"chroma", "default"}:
            try:
                from chromadb.utils import embedding_functions
            except ImportError as exc:
                raise ImportError(
                    "chromadb is required for default embeddings. "
                    "Please install it with: pip install chromadb"
                ) from exc
            return embedding_functions.DefaultEmbeddingFunction()

        raise ValueError(f"Unsupported EMBEDDING_PROVIDER: {self.provider}")

    def _batch(self, texts: List[str]) -> Iterable[List[str]]:
        for start in range(0, len(texts), self.batch_size):
            yield texts[start : start + self.batch_size]

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        embedder = self._get_embedder()
        if hasattr(embedder, "embed_documents"):
            return embedder.embed_documents(texts)
        if callable(embedder):
            return embedder(texts)
        raise TypeError("Embedding provider does not support batch embedding")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Return embeddings for a list of texts using batch processing."""
        if not texts:
            return []

        embeddings: List[List[float]] = []
        for batch in self._batch(texts):
            embeddings.extend(self._embed_batch(batch))
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Return an embedding for a single query text."""
        embedder = self._get_embedder()
        if hasattr(embedder, "embed_query"):
            return embedder.embed_query(text)
        embeddings = self.embed_texts([text])
        return embeddings[0] if embeddings else []

    def get_embedding_signature(self) -> Dict[str, str]:
        """Return provider + effective model name used for embeddings."""
        model_name = self.model_name
        if self.provider == "openai":
            model_name = model_name or "text-embedding-3-small"
        return {
            "embedding_provider": self.provider,
            "embedding_model": model_name or "",
        }


embedding_service = EmbeddingService(
    provider=settings.embedding_provider,
    model_name=settings.embedding_model_name,
    batch_size=settings.embedding_batch_size,
    openai_api_key=settings.OPENAI_API_KEY,
)
