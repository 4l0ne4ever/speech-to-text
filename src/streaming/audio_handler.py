"""
Audio chunk handler and validator for streaming pipeline.

Handles:
- Chunk size validation (3200-6400 bytes for 100-200ms audio)
- Buffer management
- Chunk timing control
- LINEAR16 format validation
"""

import logging
import time
from typing import Optional
from dataclasses import dataclass

from .errors import AudioChunkError

logger = logging.getLogger(__name__)


@dataclass
class AudioChunkMetrics:
    """Metrics for monitoring audio chunk processing."""
    total_chunks: int = 0
    total_bytes: int = 0
    valid_chunks: int = 0
    invalid_chunks: int = 0
    avg_chunk_size: float = 0.0
    last_chunk_time: float = 0.0


class AudioChunkValidator:
    """
    Validates audio chunks for streaming.
    
    Requirements:
    - Format: LINEAR16 (16-bit signed PCM)
    - Sample Rate: 16kHz
    - Channels: Mono
    - Chunk Size: 3200-6400 bytes (100-200ms)
    """
    
    # Chunk size limits for 16kHz mono LINEAR16
    MIN_CHUNK_SIZE = 3200  # 100ms: 16000 samples/s * 0.1s * 2 bytes
    MAX_CHUNK_SIZE = 6400  # 200ms: 16000 samples/s * 0.2s * 2 bytes
    
    # Audio format constants
    SAMPLE_RATE = 16000  # 16kHz
    BYTES_PER_SAMPLE = 2  # 16-bit = 2 bytes
    CHANNELS = 1  # Mono
    
    @classmethod
    def validate_chunk_size(cls, chunk: bytes) -> bool:
        """
        Validate chunk size is within acceptable range.
        
        Args:
            chunk: Audio chunk bytes
            
        Returns:
            True if valid, False otherwise
        """
        size = len(chunk)
        return cls.MIN_CHUNK_SIZE <= size <= cls.MAX_CHUNK_SIZE
    
    @classmethod
    def calculate_chunk_duration_ms(cls, chunk: bytes) -> float:
        """
        Calculate audio duration in milliseconds.
        
        Args:
            chunk: Audio chunk bytes
            
        Returns:
            Duration in milliseconds
        """
        num_samples = len(chunk) // cls.BYTES_PER_SAMPLE
        duration_seconds = num_samples / cls.SAMPLE_RATE
        return duration_seconds * 1000
    
    @classmethod
    def validate_chunk(cls, chunk: bytes, strict: bool = True) -> None:
        """
        Validate audio chunk meets all requirements.
        
        Args:
            chunk: Audio chunk bytes
            strict: If True, raise exception on invalid chunk.
                   If False, only log warning.
                   
        Raises:
            AudioChunkError: If chunk is invalid and strict=True
        """
        if not chunk:
            error_msg = "Empty audio chunk"
            if strict:
                raise AudioChunkError(error_msg)
            logger.warning(error_msg)
            return
        
        size = len(chunk)
        
        # Check size
        if not cls.validate_chunk_size(chunk):
            error_msg = (
                f"Invalid chunk size: {size} bytes. "
                f"Expected: {cls.MIN_CHUNK_SIZE}-{cls.MAX_CHUNK_SIZE} bytes "
                f"(100-200ms at 16kHz mono LINEAR16)"
            )
            if strict:
                raise AudioChunkError(error_msg)
            logger.warning(error_msg)
            return
        
        # Check alignment (must be even for 16-bit samples)
        if size % cls.BYTES_PER_SAMPLE != 0:
            error_msg = (
                f"Chunk size {size} not aligned to {cls.BYTES_PER_SAMPLE} bytes. "
                "LINEAR16 requires even byte count."
            )
            if strict:
                raise AudioChunkError(error_msg)
            logger.warning(error_msg)
            return
        
        duration_ms = cls.calculate_chunk_duration_ms(chunk)
        logger.debug(
            f"Valid chunk: {size} bytes, {duration_ms:.1f}ms duration"
        )


class AudioChunkHandler:
    """
    Handles audio chunk buffering and processing for streaming.
    
    Features:
    - Chunk validation
    - Buffer management (keep minimal for low latency)
    - Timing control
    - Metrics tracking
    """
    
    def __init__(
        self,
        max_buffer_size: int = 2,
        strict_validation: bool = True
    ):
        """
        Initialize audio chunk handler.
        
        Args:
            max_buffer_size: Maximum chunks to buffer (keep small for latency)
            strict_validation: Whether to raise exceptions on invalid chunks
        """
        self.max_buffer_size = max_buffer_size
        self.strict_validation = strict_validation
        self.validator = AudioChunkValidator()
        self.metrics = AudioChunkMetrics()
        self.buffer = []
        
        logger.info(
            f"AudioChunkHandler initialized: "
            f"max_buffer_size={max_buffer_size}, "
            f"strict_validation={strict_validation}"
        )
    
    def process_chunk(self, chunk: bytes) -> bool:
        """
        Process incoming audio chunk.
        
        Args:
            chunk: Raw audio bytes (LINEAR16)
            
        Returns:
            True if chunk is valid and processed, False otherwise
            
        Raises:
            AudioChunkError: If chunk is invalid and strict_validation=True
        """
        self.metrics.total_chunks += 1
        self.metrics.total_bytes += len(chunk)
        
        try:
            # Validate chunk
            self.validator.validate_chunk(chunk, strict=self.strict_validation)
            
            # Update metrics
            self.metrics.valid_chunks += 1
            self.metrics.avg_chunk_size = (
                self.metrics.total_bytes / self.metrics.total_chunks
            )
            self.metrics.last_chunk_time = time.time()
            
            # Add to buffer if not full
            if len(self.buffer) < self.max_buffer_size:
                self.buffer.append(chunk)
            else:
                logger.warning(
                    f"Buffer full ({len(self.buffer)} chunks), "
                    "dropping oldest chunk"
                )
                self.buffer.pop(0)
                self.buffer.append(chunk)
            
            return True
            
        except AudioChunkError as e:
            self.metrics.invalid_chunks += 1
            logger.error(f"Invalid audio chunk: {e}")
            if self.strict_validation:
                raise
            return False
    
    def get_buffered_chunks(self, clear: bool = True) -> list:
        """
        Get all buffered chunks.
        
        Args:
            clear: Whether to clear buffer after getting chunks
            
        Returns:
            List of audio chunk bytes
        """
        chunks = self.buffer.copy()
        if clear:
            self.buffer.clear()
        return chunks
    
    def get_metrics(self) -> AudioChunkMetrics:
        """Get current metrics."""
        return self.metrics
    
    def reset_metrics(self):
        """Reset metrics counters."""
        self.metrics = AudioChunkMetrics()
        logger.debug("Audio chunk metrics reset")
