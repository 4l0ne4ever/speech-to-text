"""
Semantic Matcher using Embeddings

Matches based on semantic similarity using pre-computed embeddings.
"""

from typing import List, Dict, Tuple, Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


class SemanticMatcher:
    """
    Semantic matching using embedding similarity.
    
    Finds slides with similar meaning even when exact words differ.
    """
    
    def __init__(self,
                 embedding_generator,
                 min_similarity: float = 0.7):
        """
        Initialize semantic matcher.
        
        Args:
            embedding_generator: EmbeddingGenerator instance with preloaded embeddings
            min_similarity: Minimum cosine similarity threshold
        """
        self.embedding_generator = embedding_generator
        self.min_similarity = min_similarity
        
        if embedding_generator.embeddings is None:
            raise ValueError("EmbeddingGenerator must have embeddings loaded")
            
        logger.info(f"Initialized SemanticMatcher with {len(embedding_generator.slide_ids)} slides")
        
    def match(self, query_text: str, top_k: int = 5) -> Dict[int, Dict[str, any]]:
        """
        Find slides semantically similar to query text.
        
        Args:
            query_text: Text to match
            top_k: Maximum number of results
            
        Returns:
            Dict mapping slide_id to match details
        """
        # Find similar slides
        results = self.embedding_generator.find_similar(
            query_text=query_text,
            top_k=top_k,
            min_similarity=self.min_similarity
        )
        
        # Convert to match format
        slide_matches = {}
        for slide_id, matched_text, similarity in results:
            slide_matches[slide_id] = {
                'score': similarity,
                'matched_text': matched_text,
                'similarity': similarity,
                'match_type': 'semantic',
                'match_count': 1
            }
            
        return slide_matches
        
    def match_batch(self,
                   query_texts: List[str],
                   top_k_per_query: int = 3) -> Dict[int, Dict[str, any]]:
        """
        Match multiple query texts and aggregate results.
        
        Args:
            query_texts: List of texts to match
            top_k_per_query: Top results per query
            
        Returns:
            Aggregated match results
        """
        aggregated_matches: Dict[int, Dict[str, any]] = {}
        
        for query_text in query_texts:
            matches = self.match(query_text, top_k=top_k_per_query)
            
            # Aggregate
            for slide_id, data in matches.items():
                if slide_id not in aggregated_matches:
                    aggregated_matches[slide_id] = {
                        'score': 0.0,
                        'matched_texts': [],
                        'similarities': [],
                        'match_count': 0
                    }
                    
                aggregated_matches[slide_id]['score'] += data['score']
                aggregated_matches[slide_id]['matched_texts'].append(data['matched_text'])
                aggregated_matches[slide_id]['similarities'].append(data['similarity'])
                aggregated_matches[slide_id]['match_count'] += 1
                
        return aggregated_matches
        
    def get_top_slides(self,
                      query_text: str,
                      top_k: int = 5) -> List[Tuple[int, float, str]]:
        """
        Get top semantically similar slides.
        
        Args:
            query_text: Text to match
            top_k: Number of results
            
        Returns:
            List of (slide_id, similarity, matched_text) tuples
        """
        matches = self.match(query_text, top_k=top_k)
        
        results = [
            (slide_id, data['similarity'], data['matched_text'])
            for slide_id, data in matches.items()
        ]
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
        
    def calculate_slide_similarity(self,
                                   query_text: str,
                                   slide_id: int) -> Optional[float]:
        """
        Calculate similarity score for a specific slide.
        
        Args:
            query_text: Text to match
            slide_id: Target slide ID
            
        Returns:
            Similarity score or None if slide not found
        """
        # Find the slide's text
        slide_idx = None
        for idx, sid in enumerate(self.embedding_generator.slide_ids):
            if sid == slide_id:
                slide_idx = idx
                break
                
        if slide_idx is None:
            return None
            
        # Get embeddings
        query_embedding = self.embedding_generator.model.encode(
            [query_text],
            convert_to_numpy=True
        )[0]
        
        slide_embedding = self.embedding_generator.embeddings[slide_idx]
        
        # Calculate cosine similarity
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        slide_norm = slide_embedding / np.linalg.norm(slide_embedding)
        
        similarity = float(np.dot(query_norm, slide_norm))
        
        return similarity
