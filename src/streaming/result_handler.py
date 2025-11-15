"""
Streaming result handler for managing interim and final transcription results.

Handles:
- Interim vs Final result distinction
- State management (current interim, final results list)
- Result forwarding to consumers
- Timestamp tracking
- Slide matching and highlighting (Phase 4)
"""

import logging
import time
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import tempfile

from ..slide_processing import SlideProcessor, PDFProcessingError

logger = logging.getLogger(__name__)


@dataclass
class StreamingResult:
    """
    Represents a streaming transcription result (interim or final).
    """
    text: str
    is_final: bool
    confidence: float
    timestamp: float = field(default_factory=time.time)
    words: List[dict] = field(default_factory=list)
    slide_id: Optional[int] = None
    slide_score: float = 0.0
    slide_confidence: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "text": self.text,
            "is_final": self.is_final,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "words": self.words,
        }
        
        # Add slide matching info if available
        if self.slide_id is not None:
            result["slide"] = {
                "slide_id": self.slide_id,
                "score": self.slide_score,
                "confidence": self.slide_confidence,
                "matched_keywords": self.matched_keywords
            }
        
        return result


@dataclass
class ResultMetrics:
    """Metrics for monitoring result processing."""
    total_interim_results: int = 0
    total_final_results: int = 0
    avg_confidence: float = 0.0
    last_result_time: float = 0.0
    interim_to_final_ratio: float = 0.0


class StreamingResultHandler:
    """
    Manages streaming transcription results with slide matching.
    
    Key responsibilities:
    - Track current interim result (replace on new interim)
    - Commit final results to storage
    - Forward results to consumers (UI, storage, etc.)
    - Calculate metrics
    - Match transcript segments to PDF slides in real-time (<200ms)
    """
    
    def __init__(
        self,
        result_callback: Optional[Callable] = None,
        enable_slide_matching: bool = False
    ):
        """
        Initialize result handler.
        
        Args:
            result_callback: Optional callback function to forward results.
                           Called with (result: StreamingResult) -> None
            enable_slide_matching: Enable real-time slide matching (Phase 4)
        """
        self.result_callback = result_callback
        self.current_interim: Optional[StreamingResult] = None
        self.final_results: List[StreamingResult] = []
        self.metrics = ResultMetrics()
        
        # Slide matching (Phase 4)
        self.enable_slide_matching = enable_slide_matching
        self.slide_processor: Optional[SlideProcessor] = None
        self.slides_loaded = False
        self.match_latencies: List[float] = []
        
        logger.info(
            f"StreamingResultHandler initialized "
            f"(slide_matching={enable_slide_matching})"
        )
    
    def preload_slides(
        self,
        pdf_path: str,
        storage_service = None,
        use_embeddings: bool = False
    ) -> Dict:
        """
        Preload PDF slides for real-time matching.
        
        This should be called once at session start to build indexes
        and prepare for fast matching (<200ms per segment).
        
        Args:
            pdf_path: Path to PDF file (local or GCS URI)
            storage_service: Optional GCS storage service for downloading
            use_embeddings: Whether to generate embeddings (adds ~3s startup)
            
        Returns:
            dict with slide_count, keywords_count, has_embeddings
            
        Raises:
            PDFProcessingError: If PDF processing fails
        """
        if not self.enable_slide_matching:
            logger.warning("Slide matching not enabled")
            return {}
        
        logger.info(f"Preloading slides from: {pdf_path}")
        start_time = time.time()
        
        # Download from GCS if needed
        local_path = pdf_path
        cleanup_temp = False
        
        if pdf_path.startswith('gs://'):
            if not storage_service:
                raise PDFProcessingError("storage_service required for GCS URIs")
            
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                local_path = tmp.name
                cleanup_temp = True
            
            storage_service.download_file(pdf_path, local_path)
            logger.debug(f"Downloaded PDF to {local_path}")
        
        try:
            # Initialize slide processor
            self.slide_processor = SlideProcessor(
                exact_weight=1.0,
                fuzzy_weight=0.7,
                semantic_weight=0.7,
                title_boost=2.0,
                temporal_boost=0.15,  # Higher for streaming (reduce flicker)
                min_score_threshold=1.5,
                switch_multiplier=1.2,  # Slightly higher threshold to switch
                use_embeddings=use_embeddings
            )
            
            # Process PDF and build indexes
            stats = self.slide_processor.process_pdf(local_path)
            self.slides_loaded = True
            
            load_time = time.time() - start_time
            logger.info(
                f"Slides preloaded in {load_time:.2f}s: "
                f"{stats['slide_count']} slides, "
                f"{stats['keywords_count']} keywords, "
                f"embeddings={stats['has_embeddings']}"
            )
            
            return stats
            
        finally:
            # Clean up temp file
            if cleanup_temp:
                try:
                    Path(local_path).unlink()
                except Exception:
                    pass
    
    def _match_slide(self, text: str, timestamp: float) -> Optional[Dict]:
        """
        Match transcript segment to slide (fast path for streaming).
        
        Target: <200ms latency
        
        Args:
            text: Transcript text
            timestamp: Segment timestamp for temporal smoothing
            
        Returns:
            dict with slide_id, score, confidence, keywords, latency
            or None if no match
        """
        if not self.slides_loaded or not self.slide_processor:
            return None
        
        start_time = time.time()
        
        try:
            match_result = self.slide_processor.match_segment(text, timestamp)
            
            latency = (time.time() - start_time) * 1000  # Convert to ms
            self.match_latencies.append(latency)
            
            if match_result:
                return {
                    'slide_id': match_result.slide_id,
                    'score': match_result.score,
                    'confidence': match_result.confidence,
                    'matched_keywords': match_result.matched_keywords,
                    'latency_ms': latency
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Slide matching error: {e}")
            return None
    
    def handle_interim_result(
        self,
        text: str,
        confidence: float,
        words: Optional[List[dict]] = None
    ) -> StreamingResult:
        """
        Handle interim (non-final) result.
        
        Interim results are preliminary transcriptions that can change
        as more audio arrives. The current interim is replaced with each
        new interim result.
        
        Args:
            text: Transcribed text
            confidence: Confidence score (0.0-1.0)
            words: Optional word-level details
            
        Returns:
            StreamingResult object
        """
        result = StreamingResult(
            text=text,
            is_final=False,
            confidence=confidence,
            words=words or []
        )
        
        # Replace current interim
        self.current_interim = result
        
        # Update metrics
        self.metrics.total_interim_results += 1
        self.metrics.last_result_time = time.time()
        
        # Forward to consumer
        if self.result_callback:
            try:
                self.result_callback(result)
            except Exception as e:
                logger.error(f"Error in result callback: {e}", exc_info=True)
        
        logger.debug(
            f"Interim result: '{text[:50]}...' "
            f"(confidence={confidence:.2f})"
        )
        
        return result
    
    def handle_final_result(
        self,
        text: str,
        confidence: float,
        words: Optional[List[dict]] = None,
        timestamp: Optional[float] = None
    ) -> StreamingResult:
        """
        Handle final (confirmed) result with slide matching.
        
        Final results will not change and should be committed to
        permanent storage. The current interim is cleared.
        
        Args:
            text: Transcribed text
            confidence: Confidence score (0.0-1.0)
            words: Optional word-level details
            timestamp: Optional timestamp for slide matching
            
        Returns:
            StreamingResult object with slide match if available
        """
        # Match to slide if enabled
        slide_match = None
        if self.enable_slide_matching and self.slides_loaded:
            ts = timestamp if timestamp is not None else time.time()
            slide_match = self._match_slide(text, ts)
        
        result = StreamingResult(
            text=text,
            is_final=True,
            confidence=confidence,
            words=words or [],
            slide_id=slide_match['slide_id'] if slide_match else None,
            slide_score=slide_match['score'] if slide_match else 0.0,
            slide_confidence=slide_match['confidence'] if slide_match else 0.0,
            matched_keywords=slide_match['matched_keywords'] if slide_match else []
        )
        
        # Commit to final results
        self.final_results.append(result)
        
        # Clear current interim
        self.current_interim = None
        
        # Update metrics
        self.metrics.total_final_results += 1
        self.metrics.last_result_time = time.time()
        
        # Calculate average confidence
        total_confidence = sum(r.confidence for r in self.final_results)
        self.metrics.avg_confidence = (
            total_confidence / len(self.final_results)
        )
        
        # Calculate interim-to-final ratio
        if self.metrics.total_final_results > 0:
            self.metrics.interim_to_final_ratio = (
                self.metrics.total_interim_results /
                self.metrics.total_final_results
            )
        
        # Forward to consumer
        if self.result_callback:
            try:
                self.result_callback(result)
            except Exception as e:
                logger.error(f"Error in result callback: {e}", exc_info=True)
        
        # Log with slide info
        log_msg = (
            f"Final result #{len(self.final_results)}: "
            f"'{text[:50]}...' (confidence={confidence:.2f})"
        )
        if slide_match:
            log_msg += (
                f" -> Slide {slide_match['slide_id']} "
                f"(score={slide_match['score']:.2f}, "
                f"latency={slide_match['latency_ms']:.1f}ms)"
            )
        logger.info(log_msg)
        
        return result
    
    def get_current_interim(self) -> Optional[StreamingResult]:
        """Get the current interim result, if any."""
        return self.current_interim
    
    def get_final_results(self) -> List[StreamingResult]:
        """Get all final results."""
        return self.final_results.copy()
    
    def get_full_transcript(self) -> str:
        """
        Get concatenated transcript from all final results.
        
        Returns:
            Full transcript text
        """
        return " ".join(r.text for r in self.final_results)
    
    def get_metrics(self) -> ResultMetrics:
        """Get current metrics."""
        return self.metrics
    
    def reset(self):
        """Reset handler state (for new session)."""
        self.current_interim = None
        self.final_results.clear()
        self.metrics = ResultMetrics()
        self.match_latencies.clear()
        self.slides_loaded = False
        self.slide_processor = None
        logger.debug("Result handler reset")
    
    def get_slide_timeline(self) -> List[Dict]:
        """
        Generate slide timeline from matched segments.
        
        Returns:
            List of timeline entries with slide_id, start_time, end_time
        """
        if not self.enable_slide_matching or not self.slides_loaded:
            return []
        
        # Convert results to timeline format
        matched_segments = []
        for result in self.final_results:
            if result.slide_id is not None:
                matched_segments.append({
                    'slide_id': result.slide_id,
                    'start_time': result.timestamp,
                    'end_time': result.timestamp + 2.0,  # Estimate 2s duration
                    'confidence': result.slide_confidence
                })
        
        if not matched_segments or not self.slide_processor:
            return []
        
        return self.slide_processor.generate_timeline(matched_segments)
    
    def get_matching_stats(self) -> Dict:
        """
        Get slide matching performance statistics.
        
        Returns:
            dict with match_rate, avg_latency, max_latency, etc.
        """
        if not self.enable_slide_matching:
            return {}
        
        matched_count = sum(1 for r in self.final_results if r.slide_id is not None)
        total_count = len(self.final_results)
        
        stats = {
            'enabled': self.slides_loaded,
            'total_segments': total_count,
            'matched_segments': matched_count,
            'match_rate': matched_count / total_count if total_count > 0 else 0.0
        }
        
        if self.match_latencies:
            stats['avg_latency_ms'] = sum(self.match_latencies) / len(self.match_latencies)
            stats['max_latency_ms'] = max(self.match_latencies)
            stats['min_latency_ms'] = min(self.match_latencies)
            stats['latency_p95_ms'] = sorted(self.match_latencies)[int(len(self.match_latencies) * 0.95)]
        
        return stats
    
    def export_results(self) -> dict:
        """
        Export all results for storage.
        
        Returns:
            Dictionary with full transcript, segments, metadata, and slide timeline
        """
        result = {
            "full_transcript": self.get_full_transcript(),
            "segments": [r.to_dict() for r in self.final_results],
            "metrics": {
                "total_segments": len(self.final_results),
                "avg_confidence": self.metrics.avg_confidence,
                "total_interim_results": self.metrics.total_interim_results,
                "total_final_results": self.metrics.total_final_results,
                "interim_to_final_ratio": self.metrics.interim_to_final_ratio,
            },
            "exported_at": datetime.utcnow().isoformat(),
        }
        
        # Add slide matching data if enabled
        if self.enable_slide_matching and self.slides_loaded:
            result["slide_timeline"] = self.get_slide_timeline()
            result["slide_matching_stats"] = self.get_matching_stats()
        
        return result
