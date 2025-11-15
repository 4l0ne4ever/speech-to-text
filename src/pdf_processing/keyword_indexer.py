"""
Keyword Indexer with TF-IDF Scoring

Builds inverted index for fast keyword lookup and ranks keywords by importance.
"""

from typing import List, Dict, Set, Tuple
from collections import defaultdict, Counter
import math
import logging

logger = logging.getLogger(__name__)


class KeywordIndexer:
    """
    Build keyword index with TF-IDF scoring.
    
    Creates an inverted index mapping keywords to their locations in slides,
    with importance scores based on TF-IDF.
    """
    
    def __init__(self, min_keyword_length: int = 2):
        """
        Initialize keyword indexer.
        
        Args:
            min_keyword_length: Minimum length for keywords
        """
        self.min_keyword_length = min_keyword_length
        self.inverted_index: Dict[str, List[Tuple[int, int, float]]] = defaultdict(list)
        self.document_count = 0
        self.keyword_df: Dict[str, int] = Counter()  # Document frequency
        
    def build_index(self, 
                   slide_keywords: List[List[str]],
                   slide_ids: List[int]) -> Dict[str, List[Tuple[int, int, float]]]:
        """
        Build inverted index from slide keywords.
        
        Args:
            slide_keywords: List of keyword lists (one per slide)
            slide_ids: List of slide IDs
            
        Returns:
            Inverted index: {keyword: [(slide_id, position, tf-idf)]}
        """
        if len(slide_keywords) != len(slide_ids):
            raise ValueError("slide_keywords and slide_ids must have same length")
            
        self.document_count = len(slide_ids)
        self.inverted_index = defaultdict(list)
        self.keyword_df = Counter()
        
        # First pass: Calculate document frequency
        for keywords in slide_keywords:
            unique_keywords = set(keywords)
            for keyword in unique_keywords:
                if len(keyword) >= self.min_keyword_length:
                    self.keyword_df[keyword] += 1
                    
        # Second pass: Calculate TF-IDF and build index
        for slide_id, keywords in zip(slide_ids, slide_keywords):
            # Calculate term frequency for this slide
            keyword_counts = Counter(keywords)
            total_keywords = len(keywords)
            
            if total_keywords == 0:
                continue
                
            # Add to inverted index with TF-IDF score
            for position, keyword in enumerate(keywords):
                if len(keyword) < self.min_keyword_length:
                    continue
                    
                tf = keyword_counts[keyword] / total_keywords
                idf = self._calculate_idf(keyword)
                tfidf = tf * idf
                
                self.inverted_index[keyword].append((slide_id, position, tfidf))
                
        logger.info(f"Built index with {len(self.inverted_index)} unique keywords "
                   f"across {self.document_count} slides")
        
        return dict(self.inverted_index)
        
    def _calculate_idf(self, keyword: str) -> float:
        """Calculate inverse document frequency"""
        df = self.keyword_df.get(keyword, 0)
        if df == 0:
            return 0.0
        return math.log(self.document_count / df)
        
    def lookup(self, keyword: str) -> List[Tuple[int, int, float]]:
        """
        Look up keyword in index.
        
        Args:
            keyword: Keyword to look up
            
        Returns:
            List of (slide_id, position, tf-idf) tuples
        """
        return self.inverted_index.get(keyword, [])
        
    def get_top_keywords(self, 
                        slide_keywords: List[str],
                        top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Get top keywords by TF-IDF score for a slide.
        
        Args:
            slide_keywords: Keywords from a slide
            top_k: Number of top keywords to return
            
        Returns:
            List of (keyword, tf-idf) tuples
        """
        keyword_counts = Counter(slide_keywords)
        total_keywords = len(slide_keywords)
        
        if total_keywords == 0:
            return []
            
        # Calculate TF-IDF for each keyword
        keyword_scores = []
        for keyword, count in keyword_counts.items():
            if len(keyword) < self.min_keyword_length:
                continue
                
            tf = count / total_keywords
            idf = self._calculate_idf(keyword)
            tfidf = tf * idf
            keyword_scores.append((keyword, tfidf))
            
        # Sort by TF-IDF score
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        
        return keyword_scores[:top_k]
        
    def calculate_slide_scores(self, 
                              query_keywords: List[str]) -> Dict[int, float]:
        """
        Calculate relevance scores for all slides given query keywords.
        
        Args:
            query_keywords: Keywords from query/transcript segment
            
        Returns:
            Dict mapping slide_id to relevance score
        """
        slide_scores: Dict[int, float] = defaultdict(float)
        
        for keyword in query_keywords:
            if len(keyword) < self.min_keyword_length:
                continue
                
            matches = self.lookup(keyword)
            for slide_id, position, tfidf in matches:
                slide_scores[slide_id] += tfidf
                
        return dict(slide_scores)
        
    def get_index_stats(self) -> Dict[str, any]:
        """Get statistics about the index"""
        return {
            "total_keywords": len(self.inverted_index),
            "total_slides": self.document_count,
            "avg_keywords_per_slide": sum(self.keyword_df.values()) / max(self.document_count, 1),
            "top_keywords": sorted(self.keyword_df.items(), key=lambda x: x[1], reverse=True)[:20]
        }
        
    def save_index(self, filepath: str):
        """Save index to file"""
        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump({
                'inverted_index': dict(self.inverted_index),
                'document_count': self.document_count,
                'keyword_df': dict(self.keyword_df),
                'min_keyword_length': self.min_keyword_length
            }, f)
        logger.info(f"Saved index to {filepath}")
        
    @classmethod
    def load_index(cls, filepath: str) -> 'KeywordIndexer':
        """Load index from file"""
        import pickle
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            
        indexer = cls(min_keyword_length=data['min_keyword_length'])
        indexer.inverted_index = defaultdict(list, data['inverted_index'])
        indexer.document_count = data['document_count']
        indexer.keyword_df = Counter(data['keyword_df'])
        
        logger.info(f"Loaded index from {filepath}")
        return indexer
