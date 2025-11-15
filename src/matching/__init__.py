"""
Matching Module for Transcript-Slide Synchronization

Implements multi-pass matching algorithm:
1. Exact keyword matching
2. Fuzzy matching (Levenshtein distance)
3. Semantic matching (embedding similarity)
4. Score combination with temporal smoothing
"""

from .exact_matcher import ExactMatcher
from .fuzzy_matcher import FuzzyMatcher
from .semantic_matcher import SemanticMatcher
from .score_combiner import ScoreCombiner, MatchResult

__all__ = [
    'ExactMatcher',
    'FuzzyMatcher',
    'SemanticMatcher',
    'ScoreCombiner',
    'MatchResult',
]
