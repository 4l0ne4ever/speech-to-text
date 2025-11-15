"""
Exact Keyword Matcher

Fast matching using inverted index lookup for exact keyword matches.
"""

from typing import List, Dict, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class ExactMatcher:
    """
    Exact keyword matching using inverted index.
    
    Provides fast lookup of slides containing specific keywords
    with TF-IDF based scoring.
    """
    
    def __init__(self, inverted_index: Dict[str, List[Tuple[int, int, float]]]):
        """
        Initialize exact matcher with prebuilt inverted index.
        
        Args:
            inverted_index: Inverted index {keyword: [(slide_id, position, tf-idf)]}
        """
        self.inverted_index = inverted_index
        self.total_keywords = len(inverted_index)
        logger.info(f"Initialized ExactMatcher with {self.total_keywords} keywords")
        
    def match(self, keywords: List[str]) -> Dict[int, Dict[str, any]]:
        """
        Find slides matching given keywords.
        
        Args:
            keywords: List of keywords to match
            
        Returns:
            Dict mapping slide_id to match details:
            {
                slide_id: {
                    'score': float,  # Sum of TF-IDF scores
                    'matched_keywords': List[str],  # Keywords that matched
                    'positions': List[int],  # Positions in slide
                    'match_count': int  # Number of matches
                }
            }
        """
        slide_matches: Dict[int, Dict[str, any]] = defaultdict(lambda: {
            'score': 0.0,
            'matched_keywords': [],
            'positions': [],
            'match_count': 0
        })
        
        for keyword in keywords:
            # Lookup in index
            matches = self.inverted_index.get(keyword, [])
            
            for slide_id, position, tfidf_score in matches:
                slide_matches[slide_id]['score'] += tfidf_score
                slide_matches[slide_id]['matched_keywords'].append(keyword)
                slide_matches[slide_id]['positions'].append(position)
                slide_matches[slide_id]['match_count'] += 1
                
        return dict(slide_matches)
        
    def match_single_keyword(self, keyword: str) -> List[Tuple[int, float]]:
        """
        Find slides matching a single keyword.
        
        Args:
            keyword: Keyword to match
            
        Returns:
            List of (slide_id, tf-idf) tuples
        """
        matches = self.inverted_index.get(keyword, [])
        return [(slide_id, tfidf) for slide_id, _, tfidf in matches]
        
    def get_top_slides(self, 
                      keywords: List[str],
                      top_k: int = 5) -> List[Tuple[int, float, List[str]]]:
        """
        Get top matching slides for keywords.
        
        Args:
            keywords: List of keywords
            top_k: Number of top slides to return
            
        Returns:
            List of (slide_id, score, matched_keywords) tuples
        """
        matches = self.match(keywords)
        
        # Sort by score
        sorted_matches = sorted(
            matches.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        # Convert to result format
        results = [
            (slide_id, data['score'], data['matched_keywords'])
            for slide_id, data in sorted_matches[:top_k]
        ]
        
        return results
        
    def calculate_coverage(self, keywords: List[str]) -> float:
        """
        Calculate what percentage of keywords have matches.
        
        Args:
            keywords: List of keywords
            
        Returns:
            Coverage ratio [0, 1]
        """
        if not keywords:
            return 0.0
            
        matched = sum(1 for kw in keywords if kw in self.inverted_index)
        return matched / len(keywords)
