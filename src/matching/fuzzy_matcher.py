"""
Fuzzy Matcher for Handling Variations

Matches keywords with small differences using Levenshtein distance
and phonetic similarity (hiragana comparison).
"""

from typing import List, Dict, Tuple, Set
import Levenshtein
import logging

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """
    Fuzzy keyword matching for handling speech recognition errors
    and variations.
    
    Uses:
    - Levenshtein distance for string similarity
    - Hiragana reading comparison for phonetic similarity
    """
    
    def __init__(self,
                 slide_keywords: Dict[int, List[str]],
                 slide_readings: Dict[int, List[str]] = None,
                 similarity_threshold: float = 0.8,
                 discount_factor: float = 0.7):
        """
        Initialize fuzzy matcher.
        
        Args:
            slide_keywords: Dict mapping slide_id to keywords
            slide_readings: Dict mapping slide_id to hiragana readings
            similarity_threshold: Minimum similarity to consider a match
            discount_factor: Score multiplier for fuzzy matches (< 1.0)
        """
        self.slide_keywords = slide_keywords
        self.slide_readings = slide_readings or {}
        self.similarity_threshold = similarity_threshold
        self.discount_factor = discount_factor
        
        # Build lookup for fast fuzzy matching
        self._build_keyword_lookup()
        
        logger.info(f"Initialized FuzzyMatcher with {len(slide_keywords)} slides")
        
    def _build_keyword_lookup(self):
        """Build flat keyword list for fast fuzzy search"""
        self.all_keywords: List[Tuple[int, str]] = []  # (slide_id, keyword)
        self.all_readings: List[Tuple[int, str]] = []  # (slide_id, reading)
        
        for slide_id, keywords in self.slide_keywords.items():
            for keyword in keywords:
                self.all_keywords.append((slide_id, keyword))
                
        for slide_id, readings in self.slide_readings.items():
            for reading in readings:
                self.all_readings.append((slide_id, reading))
                
    def match(self, 
             query_keywords: List[str],
             query_readings: List[str] = None) -> Dict[int, Dict[str, any]]:
        """
        Find slides with fuzzy keyword matches.
        
        Args:
            query_keywords: Keywords to match
            query_readings: Hiragana readings (optional, for phonetic matching)
            
        Returns:
            Dict mapping slide_id to match details
        """
        slide_matches: Dict[int, Dict[str, any]] = {}
        
        for query_keyword in query_keywords:
            # Try string similarity
            string_matches = self._fuzzy_match_string(query_keyword)
            self._merge_matches(slide_matches, string_matches, 'string')
            
            # Try phonetic similarity if readings available
            if query_readings:
                for query_reading in query_readings:
                    phonetic_matches = self._fuzzy_match_phonetic(query_reading)
                    self._merge_matches(slide_matches, phonetic_matches, 'phonetic')
                    
        return slide_matches
        
    def _fuzzy_match_string(self, query: str) -> List[Tuple[int, str, float]]:
        """
        Find fuzzy matches based on string similarity.
        
        Returns:
            List of (slide_id, matched_keyword, similarity) tuples
        """
        matches = []
        
        for slide_id, keyword in self.all_keywords:
            similarity = self._string_similarity(query, keyword)
            
            if similarity >= self.similarity_threshold:
                matches.append((slide_id, keyword, similarity))
                
        return matches
        
    def _fuzzy_match_phonetic(self, query_reading: str) -> List[Tuple[int, str, float]]:
        """
        Find fuzzy matches based on phonetic similarity (hiragana).
        
        Returns:
            List of (slide_id, matched_reading, similarity) tuples
        """
        matches = []
        
        for slide_id, reading in self.all_readings:
            similarity = self._string_similarity(query_reading, reading)
            
            if similarity >= self.similarity_threshold:
                matches.append((slide_id, reading, similarity))
                
        return matches
        
    def _string_similarity(self, s1: str, s2: str) -> float:
        """
        Calculate normalized string similarity.
        
        Uses Levenshtein ratio (1 - distance/max_length).
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity score [0, 1]
        """
        if not s1 or not s2:
            return 0.0
            
        # Levenshtein ratio
        return Levenshtein.ratio(s1, s2)
        
    def _merge_matches(self,
                      slide_matches: Dict[int, Dict[str, any]],
                      new_matches: List[Tuple[int, str, float]],
                      match_type: str):
        """Merge new matches into slide_matches dict"""
        
        for slide_id, matched_text, similarity in new_matches:
            if slide_id not in slide_matches:
                slide_matches[slide_id] = {
                    'score': 0.0,
                    'matched_keywords': [],
                    'similarities': [],
                    'match_types': [],
                    'match_count': 0
                }
                
            # Add discounted score
            slide_matches[slide_id]['score'] += similarity * self.discount_factor
            slide_matches[slide_id]['matched_keywords'].append(matched_text)
            slide_matches[slide_id]['similarities'].append(similarity)
            slide_matches[slide_id]['match_types'].append(match_type)
            slide_matches[slide_id]['match_count'] += 1
            
    def find_similar_keywords(self,
                             query: str,
                             top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Find most similar keywords to query.
        
        Args:
            query: Query keyword
            top_k: Number of results
            
        Returns:
            List of (keyword, similarity) tuples
        """
        similarities = []
        seen = set()
        
        for _, keyword in self.all_keywords:
            if keyword not in seen:
                similarity = self._string_similarity(query, keyword)
                if similarity >= self.similarity_threshold:
                    similarities.append((keyword, similarity))
                    seen.add(keyword)
                    
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
        
    def get_top_slides(self,
                      query_keywords: List[str],
                      query_readings: List[str] = None,
                      top_k: int = 5) -> List[Tuple[int, float, List[str]]]:
        """
        Get top matching slides.
        
        Args:
            query_keywords: Keywords to match
            query_readings: Readings for phonetic matching
            top_k: Number of results
            
        Returns:
            List of (slide_id, score, matched_keywords) tuples
        """
        matches = self.match(query_keywords, query_readings)
        
        # Sort by score
        sorted_matches = sorted(
            matches.items(),
            key=lambda x: x[1]['score'],
            reverse=True
        )
        
        results = [
            (slide_id, data['score'], data['matched_keywords'])
            for slide_id, data in sorted_matches[:top_k]
        ]
        
        return results
