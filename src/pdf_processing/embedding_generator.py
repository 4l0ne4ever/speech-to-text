"""
Embedding Generator for Semantic Similarity

Generates vector embeddings for slides using sentence-transformers
and builds FAISS index for fast similarity search.
"""

from typing import List, Dict, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

# Try to import faiss, but make it optional for testing
try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    logger.warning("FAISS not available. Semantic matching will use slower numpy similarity.")
    FAISS_AVAILABLE = False


class EmbeddingGenerator:
    """
    Generate semantic embeddings for slides.
    
    Uses sentence-transformers models to create vector representations
    of slide content for semantic similarity matching.
    """
    
    def __init__(self, 
                 model_name: str = "paraphrase-multilingual-mpnet-base-v2",
                 use_faiss: bool = True):
        """
        Initialize embedding generator.
        
        Args:
            model_name: Name of sentence-transformer model
                - "paraphrase-multilingual-mpnet-base-v2": Multilingual
                - "sonoisa/sentence-bert-base-ja-mean-tokens": Japanese-specific
            use_faiss: Whether to use FAISS for fast similarity search
        """
        self.model_name = model_name
        self.use_faiss = use_faiss and FAISS_AVAILABLE
        
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        
        # Storage
        self.embeddings: Optional[np.ndarray] = None
        self.slide_ids: List[int] = []
        self.text_blocks: List[str] = []
        self.faiss_index = None
        
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")
        
    def generate_embeddings(self, 
                           texts: List[str],
                           slide_ids: List[int],
                           batch_size: int = 32) -> np.ndarray:
        """
        Generate embeddings for list of texts.
        
        Args:
            texts: List of text blocks to embed
            slide_ids: Corresponding slide IDs
            batch_size: Batch size for encoding
            
        Returns:
            Numpy array of embeddings (n_texts, embedding_dim)
        """
        if len(texts) != len(slide_ids):
            raise ValueError("texts and slide_ids must have same length")
            
        if not texts:
            logger.warning("No texts provided for embedding")
            return np.array([])
            
        logger.info(f"Generating embeddings for {len(texts)} texts")
        
        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        # Store
        self.embeddings = embeddings
        self.slide_ids = slide_ids
        self.text_blocks = texts
        
        # Build FAISS index if enabled
        if self.use_faiss:
            self._build_faiss_index(embeddings)
            
        logger.info(f"Generated embeddings with shape {embeddings.shape}")
        
        return embeddings
        
    def _build_faiss_index(self, embeddings: np.ndarray):
        """Build FAISS index for fast similarity search"""
        
        if not FAISS_AVAILABLE:
            logger.warning("FAISS not available, skipping index build")
            return
            
        # Use IndexFlatIP for inner product (cosine similarity after normalization)
        # Normalize embeddings first
        faiss.normalize_L2(embeddings)
        
        # Create index
        self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
        self.faiss_index.add(embeddings)
        
        logger.info(f"Built FAISS index with {self.faiss_index.ntotal} vectors")
        
    def find_similar(self, 
                    query_text: str,
                    top_k: int = 5,
                    min_similarity: float = 0.7) -> List[Tuple[int, str, float]]:
        """
        Find slides most similar to query text.
        
        Args:
            query_text: Query text
            top_k: Number of results to return
            min_similarity: Minimum cosine similarity threshold
            
        Returns:
            List of (slide_id, text, similarity) tuples
        """
        if self.embeddings is None:
            raise ValueError("No embeddings generated yet")
            
        # Encode query
        query_embedding = self.model.encode(
            [query_text],
            convert_to_numpy=True
        )[0]
        
        # Search
        if self.use_faiss and self.faiss_index is not None:
            results = self._faiss_search(query_embedding, top_k)
        else:
            results = self._numpy_search(query_embedding, top_k)
            
        # Filter by minimum similarity
        results = [(sid, text, sim) for sid, text, sim in results 
                  if sim >= min_similarity]
        
        return results
        
    def _faiss_search(self, 
                     query_embedding: np.ndarray,
                     top_k: int) -> List[Tuple[int, str, float]]:
        """Search using FAISS index"""
        
        # Normalize query
        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        
        # Search
        similarities, indices = self.faiss_index.search(query_embedding, top_k)
        
        # Convert to results
        results = []
        for idx, similarity in zip(indices[0], similarities[0]):
            if idx < len(self.slide_ids):  # Valid index
                results.append((
                    self.slide_ids[idx],
                    self.text_blocks[idx],
                    float(similarity)
                ))
                
        return results
        
    def _numpy_search(self, 
                     query_embedding: np.ndarray,
                     top_k: int) -> List[Tuple[int, str, float]]:
        """Search using numpy (slower fallback)"""
        
        # Calculate cosine similarities
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        embeddings_norm = self.embeddings / np.linalg.norm(self.embeddings, axis=1, keepdims=True)
        
        similarities = np.dot(embeddings_norm, query_norm)
        
        # Get top k
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Convert to results
        results = []
        for idx in top_indices:
            results.append((
                self.slide_ids[idx],
                self.text_blocks[idx],
                float(similarities[idx])
            ))
            
        return results
        
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Cosine similarity score [0, 1]
        """
        embeddings = self.model.encode([text1, text2], convert_to_numpy=True)
        
        # Normalize
        emb1 = embeddings[0] / np.linalg.norm(embeddings[0])
        emb2 = embeddings[1] / np.linalg.norm(embeddings[1])
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2)
        
        return float(similarity)
        
    def save_embeddings(self, filepath: str):
        """Save embeddings to file"""
        if self.embeddings is None:
            raise ValueError("No embeddings to save")
            
        np.savez(
            filepath,
            embeddings=self.embeddings,
            slide_ids=self.slide_ids,
            text_blocks=self.text_blocks,
            model_name=self.model_name,
            embedding_dim=self.embedding_dim
        )
        logger.info(f"Saved embeddings to {filepath}")
        
    def load_embeddings(self, filepath: str):
        """Load embeddings from file"""
        data = np.load(filepath, allow_pickle=True)
        
        self.embeddings = data['embeddings']
        self.slide_ids = data['slide_ids'].tolist()
        self.text_blocks = data['text_blocks'].tolist()
        
        # Rebuild FAISS index if needed
        if self.use_faiss:
            self._build_faiss_index(self.embeddings)
            
        logger.info(f"Loaded embeddings from {filepath}")
        logger.info(f"Embeddings shape: {self.embeddings.shape}")
