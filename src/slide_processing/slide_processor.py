"""
Slide Processor for Phase 4 Integration

Wraps Phase 4 components (PDF processing, indexing, matching) into a single
high-level interface for file and streaming pipelines.
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import tempfile

from ..pdf_processing.pdf_extractor import PDFExtractor, SlideContent
from ..pdf_processing.japanese_nlp import JapaneseNLP
from ..pdf_processing.keyword_indexer import KeywordIndexer
from ..pdf_processing.embedding_generator import EmbeddingGenerator
from ..matching.exact_matcher import ExactMatcher
from ..matching.fuzzy_matcher import FuzzyMatcher
from ..matching.semantic_matcher import SemanticMatcher
from ..matching.score_combiner import ScoreCombiner, MatchResult

logger = logging.getLogger(__name__)


class SlideProcessingError(Exception):
    """Base exception for slide processing errors."""
    pass


class PDFProcessingError(SlideProcessingError):
    """PDF extraction or parsing failed."""
    pass


class MatchingError(SlideProcessingError):
    """Slide matching failed."""
    pass


class SlideProcessor:
    """
    High-level interface for slide processing and matching.
    
    Handles complete pipeline:
    1. PDF extraction
    2. Keyword indexing
    3. Embedding generation
    4. Transcript segment matching
    5. Timeline generation
    """
    
    def __init__(
        self,
        exact_weight: float = 1.0,
        fuzzy_weight: float = 0.7,
        semantic_weight: float = 0.7,
        title_boost: float = 2.0,
        temporal_boost: float = 0.05,
        min_score_threshold: float = 1.5,
        switch_multiplier: float = 1.1,
        use_embeddings: bool = True
    ):
        """
        Initialize slide processor with matching parameters.
        
        Args:
            exact_weight: Weight for exact keyword matches (default: 1.0)
            fuzzy_weight: Weight for fuzzy matches (default: 0.7)
            semantic_weight: Weight for semantic matches (default: 0.7)
            title_boost: Multiplier for title keyword matches (default: 2.0)
            temporal_boost: Score boost for staying on current slide (default: 0.05)
            min_score_threshold: Minimum score to return a match (default: 1.5)
            switch_multiplier: Threshold multiplier for switching slides (default: 1.1)
            use_embeddings: Whether to generate and use embeddings (default: True)
        """
        self.nlp = JapaneseNLP()
        self.keyword_indexer = KeywordIndexer()
        self.use_embeddings = use_embeddings
        
        if use_embeddings:
            self.embedding_gen = EmbeddingGenerator()
        else:
            self.embedding_gen = None
        
        # Matching parameters
        self.exact_weight = exact_weight
        self.fuzzy_weight = fuzzy_weight
        self.semantic_weight = semantic_weight
        self.title_boost = title_boost
        self.temporal_boost = temporal_boost
        self.min_score_threshold = min_score_threshold
        self.switch_multiplier = switch_multiplier
        
        # Will be initialized after processing PDF
        self.exact_matcher = None
        self.fuzzy_matcher = None
        self.semantic_matcher = None
        self.score_combiner = None
        
        # Slide data
        self.slides: List[SlideContent] = []
        self.slide_texts: List[str] = []
        self.slide_keywords: Dict[int, List[str]] = {}
        
        logger.info(
            f"Initialized SlideProcessor: "
            f"weights=({exact_weight}, {fuzzy_weight}, {semantic_weight}), "
            f"embeddings={use_embeddings}"
        )
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """
        Process PDF file and build slide index.
        
        Args:
            pdf_path: Path to PDF file (local or GCS)
            
        Returns:
            dict with slide_count, keywords_count, has_embeddings
            
        Raises:
            PDFProcessingError: If PDF processing fails
        """
        logger.info(f"Processing PDF: {pdf_path}")
        
        try:
            # Extract PDF content
            extractor = PDFExtractor()
            self.slides = extractor.extract_from_file(pdf_path)
            
            if not self.slides:
                raise PDFProcessingError("No slides extracted from PDF")
            
            logger.info(f"Extracted {len(self.slides)} slides from PDF")
            
            # Process each slide
            slide_keywords_list = []
            slide_ids = []
            
            for slide in self.slides:
                # Combine title and content
                text = slide.title
                if slide.text_blocks:
                    text += " " + " ".join(block.text for block in slide.text_blocks)
                
                self.slide_texts.append(text)
                
                # Extract keywords
                keywords = self.nlp.extract_keywords(text)
                self.slide_keywords[slide.page] = keywords
                slide_keywords_list.append(keywords)
                slide_ids.append(slide.page)
                
                logger.debug(
                    f"Slide {slide.page}: {len(keywords)} keywords from "
                    f"{len(text)} chars"
                )
            
            # Build keyword index
            inverted_index = self.keyword_indexer.build_index(
                slide_keywords_list,
                slide_ids
            )
            
            logger.info(
                f"Built keyword index: {len(inverted_index)} unique keywords"
            )
            
            # Initialize matchers
            self.exact_matcher = ExactMatcher(inverted_index)
            self.fuzzy_matcher = FuzzyMatcher(
                self.slide_keywords,
                similarity_threshold=0.8
            )
            
            # Generate embeddings if enabled
            has_embeddings = False
            if self.use_embeddings and self.embedding_gen:
                try:
                    embeddings, index = self.embedding_gen.generate_embeddings(
                        self.slide_texts,
                        slide_ids
                    )
                    self.semantic_matcher = SemanticMatcher(
                        embeddings,
                        index,
                        slide_ids,
                        min_similarity=0.7
                    )
                    has_embeddings = True
                    logger.info("Generated semantic embeddings")
                except Exception as e:
                    logger.warning(f"Failed to generate embeddings: {e}")
                    self.semantic_matcher = None
            
            # Initialize score combiner
            self.score_combiner = ScoreCombiner(
                exact_weight=self.exact_weight,
                fuzzy_weight=self.fuzzy_weight,
                semantic_weight=self.semantic_weight,
                title_boost=self.title_boost,
                temporal_boost=self.temporal_boost,
                min_score_threshold=self.min_score_threshold,
                switch_multiplier=self.switch_multiplier
            )
            
            return {
                'slide_count': len(self.slides),
                'keywords_count': len(inverted_index),
                'has_embeddings': has_embeddings
            }
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise PDFProcessingError(f"Failed to process PDF: {e}")
    
    def match_segment(
        self,
        text: str,
        timestamp: Optional[float] = None
    ) -> Optional[MatchResult]:
        """
        Match a transcript segment to a slide.
        
        Args:
            text: Transcript text to match
            timestamp: Optional timestamp for temporal smoothing
            
        Returns:
            MatchResult with slide_id, score, confidence, or None if no match
            
        Raises:
            MatchingError: If matching fails
        """
        if not self.exact_matcher or not self.score_combiner:
            raise MatchingError("Slide processor not initialized. Call process_pdf() first.")
        
        try:
            # Extract keywords from transcript
            keywords = self.nlp.extract_keywords(text)
            readings = [self.nlp.get_reading(text)]
            
            # Run three-pass matching
            exact_results = self.exact_matcher.match(keywords)
            fuzzy_results = self.fuzzy_matcher.match(keywords, readings)
            
            semantic_results = {}
            if self.semantic_matcher:
                semantic_results = self.semantic_matcher.match(text, top_k=5)
            
            # Combine scores
            metadata = {}
            if timestamp is not None:
                metadata['timestamp'] = timestamp
            
            match_result = self.score_combiner.combine(
                exact_results,
                fuzzy_results,
                semantic_results,
                metadata
            )
            
            return match_result
            
        except Exception as e:
            logger.error(f"Matching failed for segment: {e}")
            raise MatchingError(f"Failed to match segment: {e}")
    
    def match_transcript(
        self,
        segments: List[Dict]
    ) -> List[Dict]:
        """
        Match all transcript segments to slides.
        
        Args:
            segments: List of dicts with 'text', 'start_time', 'end_time'
            
        Returns:
            List of dicts with original segment data plus:
                - slide_id: Matched slide number (or None)
                - score: Match score
                - confidence: Match confidence
                - matched_keywords: List of matched keywords
                
        Raises:
            MatchingError: If matching fails
        """
        logger.info(f"Matching {len(segments)} transcript segments")
        
        results = []
        matched_count = 0
        
        for segment in segments:
            text = segment.get('text', '')
            start_time = segment.get('start_time', 0.0)
            
            # Match segment
            match_result = self.match_segment(text, start_time)
            
            # Add match data to segment
            result = segment.copy()
            if match_result:
                result['slide_id'] = match_result.slide_id
                result['score'] = match_result.score
                result['confidence'] = match_result.confidence
                result['matched_keywords'] = match_result.matched_keywords
                matched_count += 1
            else:
                result['slide_id'] = None
                result['score'] = 0.0
                result['confidence'] = 0.0
                result['matched_keywords'] = []
            
            results.append(result)
        
        accuracy = matched_count / len(segments) if segments else 0.0
        logger.info(
            f"Matched {matched_count}/{len(segments)} segments "
            f"({accuracy*100:.1f}% accuracy)"
        )
        
        return results
    
    def generate_timeline(
        self,
        matched_segments: List[Dict]
    ) -> List[Dict]:
        """
        Generate slide timeline from matched segments.
        
        Consolidates consecutive segments on same slide into timeline entries.
        
        Args:
            matched_segments: Output from match_transcript()
            
        Returns:
            List of timeline entries with:
                - slide_id: Slide number
                - start_time: Timeline start time
                - end_time: Timeline end time
                - segment_count: Number of segments
                - avg_confidence: Average confidence
        """
        if not matched_segments:
            return []
        
        timeline = []
        current_slide = None
        current_start = None
        current_end = None
        current_segments = []
        
        for segment in matched_segments:
            slide_id = segment.get('slide_id')
            start_time = segment.get('start_time', 0.0)
            end_time = segment.get('end_time', 0.0)
            confidence = segment.get('confidence', 0.0)
            
            if slide_id is None:
                # No match, continue current or skip
                if current_slide is not None:
                    current_end = end_time
                continue
            
            if slide_id != current_slide:
                # Slide changed, save previous timeline entry
                if current_slide is not None:
                    avg_conf = sum(s.get('confidence', 0.0) for s in current_segments) / len(current_segments)
                    timeline.append({
                        'slide_id': current_slide,
                        'start_time': current_start,
                        'end_time': current_end,
                        'segment_count': len(current_segments),
                        'avg_confidence': avg_conf
                    })
                
                # Start new timeline entry
                current_slide = slide_id
                current_start = start_time
                current_end = end_time
                current_segments = [segment]
            else:
                # Same slide, extend timeline
                current_end = end_time
                current_segments.append(segment)
        
        # Add final timeline entry
        if current_slide is not None:
            avg_conf = sum(s.get('confidence', 0.0) for s in current_segments) / len(current_segments)
            timeline.append({
                'slide_id': current_slide,
                'start_time': current_start,
                'end_time': current_end,
                'segment_count': len(current_segments),
                'avg_confidence': avg_conf
            })
        
        logger.info(f"Generated timeline with {len(timeline)} entries")
        
        return timeline
    
    def get_slide_info(self, slide_id: int) -> Optional[Dict]:
        """
        Get information about a specific slide.
        
        Args:
            slide_id: Slide page number
            
        Returns:
            dict with title, content, keywords, or None if not found
        """
        for slide in self.slides:
            if slide.page == slide_id:
                return {
                    'slide_id': slide.page,
                    'title': slide.title,
                    'content': ' '.join(block.text for block in slide.text_blocks),
                    'keywords': self.slide_keywords.get(slide_id, [])
                }
        return None
