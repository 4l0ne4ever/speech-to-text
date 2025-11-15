"""
Real-Time Streaming Pipeline for Japanese Speech-to-Text.

This module implements Phase 3 of the Speech-to-Text system:
- Bidirectional gRPC streaming with Google Cloud Speech-to-Text V2 API
- Session management with automatic renewal
- Audio chunk handling and validation
- Interim and final result processing
- Low-latency (<800ms) real-time transcription
"""

from .session_manager import StreamingSessionManager, StreamingSession
from .audio_handler import AudioChunkHandler, AudioChunkValidator
from .result_handler import StreamingResultHandler, StreamingResult
from .session_renewer import SessionRenewer, RenewalEvent, RenewalStatus, AudioBuffer
from .audio_preprocessing import (
    AudioPreprocessor,
    VoiceActivityDetector,
    AutomaticGainControl,
    VADConfig,
    AGCConfig,
    AudioActivity,
)
from .metrics_collector import (
    MetricsCollector,
    get_metrics_collector,
)
from .alerting import (
    AlertManager,
    Alert,
    AlertConfig,
    AlertSeverity,
)
# Note: test_harness requires StreamProcessor which is not yet implemented
# from .test_harness import (
#     StreamingTestHarness,
#     TestCase,
#     TestResult,
#     StreamingPattern,
#     create_standard_test_suite,
# )
from .errors import (
    StreamingError,
    SessionTimeoutError,
    AudioChunkError,
    StreamInterruptedError,
)

__all__ = [
    # Core streaming
    "StreamingSessionManager",
    "StreamingSession",
    "AudioChunkHandler",
    "AudioChunkValidator",
    "StreamingResultHandler",
    "StreamingResult",
    
    # Session renewal
    "SessionRenewer",
    "RenewalEvent",
    "RenewalStatus",
    "AudioBuffer",
    
    # Audio preprocessing
    "AudioPreprocessor",
    "VoiceActivityDetector",
    "AutomaticGainControl",
    "VADConfig",
    "AGCConfig",
    "AudioActivity",
    
    # Monitoring
    "MetricsCollector",
    "get_metrics_collector",
    "AlertManager",
    "Alert",
    "AlertConfig",
    "AlertSeverity",
    
    # Testing (not yet available - requires StreamProcessor)
    # "StreamingTestHarness",
    # "TestCase",
    # "TestResult",
    # "StreamingPattern",
    # "create_standard_test_suite",
    
    # Errors
    "StreamingError",
    "SessionTimeoutError",
    "AudioChunkError",
    "StreamInterruptedError",
]
