"""
Score Combiner with Temporal Smoothing

Combines scores from exact, fuzzy, and semantic matching
with temporal smoothing to prevent flickering.
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of slide matching"""
    slide_id: int
    score: float
    confidence: float
    matched_keywords: List[str]
    match_types: List[str]  # 'exact', 'fuzzy', 'semantic'
    positions: List[int]  # Character positions in slide
    is_high_confidence: bool
    
    
class ScoreCombiner:
    """
    Combine scores from multiple matchers with temporal smoothing.
    
    Implements weighted scoring:
    - Exact matches: weight 1.0 (highest confidence)
    - Fuzzy matches: weight 0.7 (good confidence)
    - Semantic matches: weight 0.5 (conceptual similarity)
    
    Plus boosting factors:
    - Title match: 1.5x boost
    - Temporal continuity: 0.3 boost for current slide
    """
    
    def __init__(self,
                 exact_weight: float = 1.0,
                 fuzzy_weight: float = 0.7,
                 semantic_weight: float = 0.7,
                 title_boost: float = 2.0,
                 temporal_boost: float = 0.05,  # Minimal temporal boost
                 min_score_threshold: float = 1.5,
                 switch_multiplier: float = 1.1):  # Easy to switch slides
        """
        Initialize score combiner.
        
        Args:
            exact_weight: Weight for exact matches
            fuzzy_weight: Weight for fuzzy matches
            semantic_weight: Weight for semantic matches (increased for better context)
            title_boost: Multiplier when title matched (increased to prioritize title matches)
            temporal_boost: Additive boost for current slide (minimal to allow free transitions)
            min_score_threshold: Minimum score to return match
            switch_multiplier: New slide must score this much higher to switch (low for smooth transitions)
        """
        self.exact_weight = exact_weight
        self.fuzzy_weight = fuzzy_weight
        self.semantic_weight = semantic_weight
        self.title_boost = title_boost
        self.temporal_boost = temporal_boost
        self.min_score_threshold = min_score_threshold
        self.switch_multiplier = switch_multiplier
        
        # State for temporal smoothing
        self.current_slide_id: Optional[int] = None
        self.current_slide_score: float = 0.0
        self.match_history: List[Tuple[int, float]] = []  # (slide_id, score)
        
        logger.info(f"Initialized ScoreCombiner with weights: "
                   f"exact={exact_weight}, fuzzy={fuzzy_weight}, semantic={semantic_weight}")
        
    def combine(self,
               exact_matches: Dict[int, Dict],
               fuzzy_matches: Dict[int, Dict],
               semantic_matches: Dict[int, Dict],
               slide_metadata: Dict[int, Dict] = None) -> Optional[MatchResult]:
        """
        Combine match results from all matchers.
        
        Args:
            exact_matches: Results from ExactMatcher
            fuzzy_matches: Results from FuzzyMatcher
            semantic_matches: Results from SemanticMatcher
            slide_metadata: Optional metadata (e.g., which blocks are titles)
            
        Returns:
            Best MatchResult or None if no good match
        """
        # Combine all slide IDs
        all_slide_ids = set()
        all_slide_ids.update(exact_matches.keys())
        all_slide_ids.update(fuzzy_matches.keys())
        all_slide_ids.update(semantic_matches.keys())
        
        if not all_slide_ids:
            return None
            
        # Calculate combined scores
        slide_scores: Dict[int, Dict] = {}
        
        for slide_id in all_slide_ids:
            combined_data = self._combine_slide_scores(
                slide_id,
                exact_matches.get(slide_id, {}),
                fuzzy_matches.get(slide_id, {}),
                semantic_matches.get(slide_id, {}),
                slide_metadata.get(slide_id, {}) if slide_metadata else {}
            )
            slide_scores[slide_id] = combined_data
            
        # Apply temporal smoothing
        best_match = self._apply_temporal_smoothing(slide_scores)
        
        return best_match
        
    def _combine_slide_scores(self,
                             slide_id: int,
                             exact_data: Dict,
                             fuzzy_data: Dict,
                             semantic_data: Dict,
                             metadata: Dict) -> Dict:
        """Combine scores for a single slide"""
        
        # Calculate weighted score
        score = 0.0
        matched_keywords = []
        match_types = []
        positions = []
        
        # Exact matches
        if exact_data:
            exact_score = exact_data.get('score', 0.0) * self.exact_weight
            score += exact_score
            matched_keywords.extend(exact_data.get('matched_keywords', []))
            positions.extend(exact_data.get('positions', []))
            if exact_score > 0:
                match_types.append('exact')
                
        # Fuzzy matches
        if fuzzy_data:
            fuzzy_score = fuzzy_data.get('score', 0.0) * self.fuzzy_weight
            score += fuzzy_score
            matched_keywords.extend(fuzzy_data.get('matched_keywords', []))
            if fuzzy_score > 0:
                match_types.append('fuzzy')
                
        # Semantic matches
        if semantic_data:
            semantic_score = semantic_data.get('score', 0.0) * self.semantic_weight
            score += semantic_score
            if semantic_score > 0:
                match_types.append('semantic')
                
        # Title boost
        has_title_match = metadata.get('title_matched', False)
        if has_title_match:
            score *= self.title_boost
            
        # Normalize by slide length (optional)
        slide_length = metadata.get('text_length', 1)
        normalized_score = score / max(slide_length / 100, 1)
        
        return {
            'score': normalized_score,
            'raw_score': score,
            'matched_keywords': list(set(matched_keywords)),  # Deduplicate
            'match_types': list(set(match_types)),
            'positions': sorted(set(positions)),
            'has_title_match': has_title_match
        }
        
    def _apply_temporal_smoothing(self,
                                 slide_scores: Dict[int, Dict]) -> Optional[MatchResult]:
        """
        Apply temporal smoothing to prevent flickering.
        
        Current slide gets a boost. Only switch if new slide scores
        significantly higher (switch_multiplier).
        """
        if not slide_scores:
            return None
            
        # Boost current slide
        if self.current_slide_id and self.current_slide_id in slide_scores:
            slide_scores[self.current_slide_id]['score'] += self.temporal_boost
            
        # Find best slide
        best_slide_id = max(slide_scores.keys(), key=lambda sid: slide_scores[sid]['score'])
        best_score = slide_scores[best_slide_id]['score']
        
        # Check minimum threshold
        if best_score < self.min_score_threshold:
            logger.debug(f"Best score {best_score:.2f} below threshold {self.min_score_threshold}")
            return None
            
        # Check if we should switch slides
        should_switch = True
        if self.current_slide_id and self.current_slide_id != best_slide_id:
            # Current slide score (without temporal boost)
            current_score = slide_scores.get(self.current_slide_id, {}).get('score', 0.0)
            current_score -= self.temporal_boost  # Remove boost for comparison
            
            # Only switch if new score is significantly higher
            if best_score < current_score * self.switch_multiplier:
                should_switch = False
                best_slide_id = self.current_slide_id
                best_score = current_score + self.temporal_boost
                
        if should_switch and best_slide_id != self.current_slide_id:
            logger.info(f"Switching slide: {self.current_slide_id} -> {best_slide_id} "
                       f"(score: {best_score:.2f})")
            self.current_slide_id = best_slide_id
            self.current_slide_score = best_score
            
        # Build result
        best_data = slide_scores[best_slide_id]
        
        result = MatchResult(
            slide_id=best_slide_id,
            score=best_score,
            confidence=min(best_score / 10.0, 1.0),  # Normalize to [0, 1]
            matched_keywords=best_data['matched_keywords'],
            match_types=best_data['match_types'],
            positions=best_data['positions'],
            is_high_confidence=best_score >= self.min_score_threshold * 1.5
        )
        
        # Update history
        self.match_history.append((best_slide_id, best_score))
        if len(self.match_history) > 100:  # Keep last 100
            self.match_history = self.match_history[-100:]
            
        return result
        
    def reset(self):
        """Reset temporal state"""
        self.current_slide_id = None
        self.current_slide_score = 0.0
        self.match_history = []
        logger.info("Reset temporal state")
        
    def get_statistics(self) -> Dict:
        """Get matching statistics"""
        if not self.match_history:
            return {
                'total_matches': 0,
                'unique_slides': 0,
                'avg_score': 0.0,
                'current_slide': None
            }
            
        unique_slides = len(set(sid for sid, _ in self.match_history))
        avg_score = sum(score for _, score in self.match_history) / len(self.match_history)
        
        return {
            'total_matches': len(self.match_history),
            'unique_slides': unique_slides,
            'avg_score': avg_score,
            'current_slide': self.current_slide_id,
            'current_score': self.current_slide_score
        }
        
    def adjust_weights(self,
                      exact_weight: Optional[float] = None,
                      fuzzy_weight: Optional[float] = None,
                      semantic_weight: Optional[float] = None):
        """Dynamically adjust matching weights"""
        if exact_weight is not None:
            self.exact_weight = exact_weight
        if fuzzy_weight is not None:
            self.fuzzy_weight = fuzzy_weight
        if semantic_weight is not None:
            self.semantic_weight = semantic_weight
            
        logger.info(f"Adjusted weights: exact={self.exact_weight}, "
                   f"fuzzy={self.fuzzy_weight}, semantic={self.semantic_weight}")
