"""
Streaming result handler for managing interim and final transcription results.

Handles:
- Interim vs Final result distinction
- State management (current interim, final results list)
- Result forwarding to consumers
- Timestamp tracking
"""

import logging
import time
from typing import Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime

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
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "is_final": self.is_final,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "words": self.words,
        }


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
    Manages streaming transcription results.
    
    Key responsibilities:
    - Track current interim result (replace on new interim)
    - Commit final results to storage
    - Forward results to consumers (UI, storage, etc.)
    - Calculate metrics
    """
    
    def __init__(self, result_callback: Optional[Callable] = None):
        """
        Initialize result handler.
        
        Args:
            result_callback: Optional callback function to forward results.
                           Called with (result: StreamingResult) -> None
        """
        self.result_callback = result_callback
        self.current_interim: Optional[StreamingResult] = None
        self.final_results: List[StreamingResult] = []
        self.metrics = ResultMetrics()
        
        logger.info("StreamingResultHandler initialized")
    
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
        words: Optional[List[dict]] = None
    ) -> StreamingResult:
        """
        Handle final (confirmed) result.
        
        Final results will not change and should be committed to
        permanent storage. The current interim is cleared.
        
        Args:
            text: Transcribed text
            confidence: Confidence score (0.0-1.0)
            words: Optional word-level details
            
        Returns:
            StreamingResult object
        """
        result = StreamingResult(
            text=text,
            is_final=True,
            confidence=confidence,
            words=words or []
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
        
        logger.info(
            f"Final result #{len(self.final_results)}: "
            f"'{text[:50]}...' (confidence={confidence:.2f})"
        )
        
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
        logger.debug("Result handler reset")
    
    def export_results(self) -> dict:
        """
        Export all results for storage.
        
        Returns:
            Dictionary with full transcript, segments, and metadata
        """
        return {
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
