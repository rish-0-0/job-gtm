"""
Embedding service using sentence-transformers for semantic similarity search
"""
import logging
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Generates sentence embeddings using all-MiniLM-L6-v2 model
    384 dimensions, fast CPU inference (~40ms)
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """
        Initialize embedding model

        Args:
            model_name: Sentence transformer model to use
        """
        self.model_name = model_name
        self._model = None
        logger.info(f"[EmbeddingService] Initializing with model: {model_name}")

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the model"""
        if self._model is None:
            logger.info(f"[EmbeddingService] Loading model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info(f"[EmbeddingService] Model loaded successfully")
        return self._model

    def encode(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding (384 dimensions)
        """
        logger.debug(f"[EmbeddingService] Encoding text: {text[:100]}...")
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing)

        Args:
            texts: List of input texts

        Returns:
            List of embeddings
        """
        logger.debug(f"[EmbeddingService] Encoding batch of {len(texts)} texts")
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions"""
        return 384


# Singleton instance
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """
    Get singleton embedding service instance

    Returns:
        EmbeddingService instance
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
