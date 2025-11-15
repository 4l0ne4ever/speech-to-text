"""
Streaming-specific error classes for Phase 3 implementation.
"""


class StreamingError(Exception):
    """Base exception for streaming-related errors."""
    pass


class SessionTimeoutError(StreamingError):
    """Raised when a streaming session times out (5 min limit)."""
    pass


class AudioChunkError(StreamingError):
    """Raised when audio chunk is invalid (size, format, etc.)."""
    pass


class StreamInterruptedError(StreamingError):
    """Raised when gRPC stream is interrupted unexpectedly."""
    pass


class SessionNotFoundError(StreamingError):
    """Raised when trying to access a non-existent session."""
    pass


class SessionRenewalError(StreamingError):
    """Raised when session renewal fails."""
    pass
