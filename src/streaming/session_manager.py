"""
Streaming Session Manager for Google Cloud Speech-to-Text V2 API.

Manages:
- Session lifecycle (start, maintain, renew, close)
- Thread-safe operations
- Session state tracking
- Automatic renewal before 5-minute timeout
"""

import logging
import time
import threading
import queue
from typing import Optional, Dict, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from google.api_core import exceptions as google_exceptions

from .audio_handler import AudioChunkHandler
from .result_handler import StreamingResultHandler, StreamingResult
from .errors import (
    SessionTimeoutError,
    SessionNotFoundError,
    SessionRenewalError,
    StreamInterruptedError,
)

logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """Session status states."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    RENEWING = "renewing"
    CLOSING = "closing"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class StreamingSession:
    """
    Represents an active streaming session.
    """
    session_id: str
    presentation_id: str
    created_at: float = field(default_factory=time.time)
    status: SessionStatus = SessionStatus.INITIALIZING
    
    # Handlers
    audio_handler: Optional[AudioChunkHandler] = None
    result_handler: Optional[StreamingResultHandler] = None
    
    # gRPC stream
    stream: Optional[any] = None
    audio_queue: queue.Queue = field(default_factory=queue.Queue)  # Queue for audio chunks
    result_listener_thread: Optional[threading.Thread] = None
    stop_listener: threading.Event = field(default_factory=threading.Event)
    
    # Timing
    last_audio_time: float = field(default_factory=time.time)
    renewal_count: int = 0
    
    # Metadata
    total_chunks_sent: int = 0
    total_bytes_sent: int = 0
    
    def duration(self) -> float:
        """Get session duration in seconds."""
        return time.time() - self.created_at
    
    def time_since_last_audio(self) -> float:
        """Get time since last audio in seconds."""
        return time.time() - self.last_audio_time
    
    def should_renew(self, renewal_threshold: float = 270.0) -> bool:
        """
        Check if session should be renewed.
        
        Google closes sessions after ~5 minutes (300s) of audio or
        ~1 minute (60s) of silence. We renew at 4.5 minutes (270s).
        
        Args:
            renewal_threshold: Renewal threshold in seconds (default: 270s = 4.5 min)
            
        Returns:
            True if renewal is needed
        """
        return (
            self.status == SessionStatus.ACTIVE and
            self.duration() >= renewal_threshold
        )
    
    def to_dict(self) -> dict:
        """Export session info."""
        return {
            "session_id": self.session_id,
            "presentation_id": self.presentation_id,
            "created_at": self.created_at,
            "duration": self.duration(),
            "status": self.status.value,
            "renewal_count": self.renewal_count,
            "total_chunks_sent": self.total_chunks_sent,
            "total_bytes_sent": self.total_bytes_sent,
            "time_since_last_audio": self.time_since_last_audio(),
        }


class StreamingSessionManager:
    """
    Manages multiple concurrent streaming sessions.
    
    Thread-safe session management with automatic renewal.
    """
    
    # Session timeout limits (Google Cloud limits)
    MAX_AUDIO_DURATION_SECONDS = 300  # 5 minutes of continuous audio
    MAX_SILENCE_DURATION_SECONDS = 60  # 1 minute of silence
    RENEWAL_THRESHOLD_SECONDS = 270  # Renew at 4.5 minutes
    
    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        result_callback: Optional[Callable] = None
    ):
        """
        Initialize session manager.
        
        Args:
            credentials_path: Path to GCP service account key
            project_id: GCP project ID (required for V2 API)
            result_callback: Callback for streaming results
        """
        self.credentials_path = credentials_path
        self.project_id = project_id
        self.result_callback = result_callback
        
        # Thread-safe session storage
        self.sessions: Dict[str, StreamingSession] = {}
        self.lock = threading.Lock()
        
        # Google Cloud client (V2 API)
        self.client = SpeechClient.from_service_account_file(credentials_path) \
            if credentials_path else SpeechClient()
        
        logger.info(
            f"StreamingSessionManager initialized: "
            f"project_id={project_id}"
        )
    
    def create_session(
        self,
        session_id: str,
        presentation_id: str,
        language_code: str = "ja-JP",
        model: str = "latest_long",
        enable_interim_results: bool = True
    ) -> StreamingSession:
        """
        Create a new streaming session.
        
        Args:
            session_id: Unique session identifier
            presentation_id: Associated presentation ID
            language_code: Language code (default: ja-JP)
            model: Speech model (default: latest_long)
            enable_interim_results: Enable interim results (default: True)
            
        Returns:
            StreamingSession object
            
        Raises:
            ValueError: If session already exists
        """
        with self.lock:
            if session_id in self.sessions:
                raise ValueError(f"Session {session_id} already exists")
            
            # Create session
            session = StreamingSession(
                session_id=session_id,
                presentation_id=presentation_id,
                audio_handler=AudioChunkHandler(max_buffer_size=2),
                result_handler=StreamingResultHandler(
                    result_callback=self.result_callback
                )
            )
            
            self.sessions[session_id] = session
            
            logger.info(
                f"Session created: {session_id} "
                f"(presentation={presentation_id})"
            )
            
            return session
    
    def get_session(self, session_id: str) -> StreamingSession:
        """
        Get session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            StreamingSession object
            
        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        with self.lock:
            if session_id not in self.sessions:
                raise SessionNotFoundError(f"Session {session_id} not found")
            return self.sessions[session_id]
    
    def start_session(
        self,
        session_id: str,
        language_code: str = "ja-JP",
        model: str = "latest_long",
        enable_interim_results: bool = True
    ) -> bool:
        """
        Start (initialize) a streaming session.
        
        This opens the gRPC stream but doesn't send audio yet.
        Audio sending is done via send_audio_chunk().
        
        Args:
            session_id: Session identifier
            language_code: Language code
            model: Speech model
            enable_interim_results: Enable interim results
            
        Returns:
            True if started successfully
            
        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = self.get_session(session_id)
        
        try:
            # Build V2 streaming config
            config = self._build_streaming_config(
                language_code=language_code,
                model=model,
                enable_interim_results=enable_interim_results
            )
            
            # Create recognizer path for V2 API
            recognizer = f"projects/{self.project_id}/locations/global/recognizers/_"
            
            # Create streaming config
            streaming_config = cloud_speech.StreamingRecognitionConfig(
                config=config,
                streaming_features=cloud_speech.StreamingRecognitionFeatures(
                    interim_results=enable_interim_results
                )
            )
            
            # Create request generator that reads from queue
            def request_generator():
                # First request: config only
                yield cloud_speech.StreamingRecognizeRequest(
                    recognizer=recognizer,
                    streaming_config=streaming_config
                )
                
                # Subsequent requests: audio chunks from queue
                while not session.stop_listener.is_set():
                    try:
                        # Get chunk from queue with timeout
                        chunk = session.audio_queue.get(timeout=0.1)
                        if chunk is None:  # Sentinel value to stop
                            break
                        
                        yield cloud_speech.StreamingRecognizeRequest(
                            audio=chunk
                        )
                    except queue.Empty:
                        continue  # No audio available, keep waiting
            
            # Open bidirectional gRPC stream
            session.stream = self.client.streaming_recognize(
                requests=request_generator()
            )
            
            # Start result listener thread
            session.result_listener_thread = threading.Thread(
                target=self._result_listener,
                args=(session_id, session.stream),
                daemon=True
            )
            session.result_listener_thread.start()
            
            session.status = SessionStatus.ACTIVE
            session.last_audio_time = time.time()
            
            logger.info(
                f"Session started: {session_id} "
                f"(model={model}, language={language_code})"
            )
            
            return True
            
        except Exception as e:
            session.status = SessionStatus.ERROR
            logger.error(f"Failed to start session {session_id}: {e}")
            raise
    
    def send_audio_chunk(
        self,
        session_id: str,
        chunk: bytes
    ) -> bool:
        """
        Send audio chunk to Google Cloud.
        
        Args:
            session_id: Session identifier
            chunk: Audio bytes (LINEAR16, 16kHz, mono)
            
        Returns:
            True if sent successfully
            
        Raises:
            SessionNotFoundError: If session doesn't exist
            AudioChunkError: If chunk is invalid
        """
        session = self.get_session(session_id)
        
        if session.status != SessionStatus.ACTIVE:
            logger.warning(
                f"Cannot send audio: session {session_id} "
                f"status is {session.status.value}"
            )
            return False
        
        try:
            # Validate and process chunk
            if session.audio_handler.process_chunk(chunk):
                # Put audio chunk into queue for request generator
                try:
                    session.audio_queue.put(chunk, timeout=1.0)
                    
                    session.total_chunks_sent += 1
                    session.total_bytes_sent += len(chunk)
                    session.last_audio_time = time.time()
                    
                except queue.Full:
                    logger.error(
                        f"Audio queue full for session {session_id}, dropping chunk"
                    )
                    return False
                
                except Exception as e:
                    logger.error(
                        f"Error queuing audio for {session_id}: {e}"
                    )
                    raise StreamInterruptedError(f"Failed to queue audio: {e}")
                
                # Check if renewal needed
                if session.should_renew(self.RENEWAL_THRESHOLD_SECONDS):
                    logger.warning(
                        f"Session {session_id} approaching timeout, "
                        "renewal needed"
                    )
                    # Renewal will be handled by monitoring thread
                
                logger.debug(
                    f"Sent chunk to session {session_id}: "
                    f"{len(chunk)} bytes "
                    f"(total: {session.total_chunks_sent} chunks, "
                    f"{session.total_bytes_sent} bytes)"
                )
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(
                f"Error sending audio chunk to session {session_id}: {e}"
            )
            raise
    
    def close_session(self, session_id: str) -> dict:
        """
        Close a streaming session gracefully.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session summary dictionary
            
        Raises:
            SessionNotFoundError: If session doesn't exist
        """
        session = self.get_session(session_id)
        
        try:
            session.status = SessionStatus.CLOSING
            
            # Stop result listener thread
            if session.result_listener_thread:
                # Send sentinel value to stop request generator
                session.audio_queue.put(None)
                session.stop_listener.set()
                session.result_listener_thread.join(timeout=5.0)
                if session.result_listener_thread.is_alive():
                    logger.warning(
                        f"Result listener thread for {session_id} "
                        "did not stop gracefully"
                    )
            
            # Close gRPC stream if open
            if session.stream:
                try:
                    session.stream.cancel()
                    logger.debug(f"gRPC stream closed for {session_id}")
                except Exception as e:
                    logger.warning(
                        f"Error closing gRPC stream for {session_id}: {e}"
                    )
            
            # Export results
            summary = {
                "session": session.to_dict(),
                "results": session.result_handler.export_results(),
                "audio_metrics": session.audio_handler.get_metrics(),
            }
            
            session.status = SessionStatus.CLOSED
            
            # Remove from active sessions
            with self.lock:
                del self.sessions[session_id]
            
            logger.info(
                f"Session closed: {session_id} "
                f"(duration={session.duration():.1f}s, "
                f"chunks={session.total_chunks_sent})"
            )
            
            return summary
            
        except Exception as e:
            session.status = SessionStatus.ERROR
            logger.error(f"Error closing session {session_id}: {e}")
            raise
    
    def get_active_sessions(self) -> Dict[str, StreamingSession]:
        """Get all active sessions."""
        with self.lock:
            return {
                sid: s for sid, s in self.sessions.items()
                if s.status == SessionStatus.ACTIVE
            }
    
    def get_session_count(self) -> int:
        """Get total number of active sessions."""
        return len(self.sessions)
    
    def _build_streaming_config(
        self,
        language_code: str,
        model: str,
        enable_interim_results: bool
    ) -> cloud_speech.RecognitionConfig:
        """
        Build V2 API streaming recognition config.
        
        Args:
            language_code: Language code (ja-JP)
            model: Speech model (latest_long)
            enable_interim_results: Enable interim results
            
        Returns:
            RecognitionConfig for V2 streaming API
        """
        # V2 API audio format config
        explicit_decoding_config = cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            audio_channel_count=1,
        )
        
        # V2 API recognition features
        features = cloud_speech.RecognitionFeatures(
            enable_automatic_punctuation=True,
            enable_word_time_offsets=True,
            enable_word_confidence=True,
        )
        
        # Build config
        config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=explicit_decoding_config,
            language_codes=[language_code],
            model=model,
            features=features,
        )
        
        return config
    
    def _result_listener(self, session_id: str, stream):
        """
        Listen to streaming results from Google Cloud in a separate thread.
        
        This runs continuously until the session is closed.
        
        Args:
            session_id: Session identifier
            stream: gRPC streaming response iterator
        """
        logger.info(f"Result listener started for session {session_id}")
        
        try:
            session = self.get_session(session_id)
            
            # Iterate over streaming responses
            for response in stream:
                if session.stop_listener.is_set():
                    logger.debug(f"Stop signal received for {session_id}")
                    break
                
                # Process each result in the response
                for result in response.results:
                    if not result.alternatives:
                        continue
                    
                    # Get top alternative
                    alternative = result.alternatives[0]
                    transcript = alternative.transcript
                    confidence = alternative.confidence if hasattr(alternative, 'confidence') else 0.0
                    
                    # Extract word-level timestamps if available
                    words = []
                    if hasattr(alternative, 'words'):
                        for word_info in alternative.words:
                            words.append({
                                "word": word_info.word,
                                "start_time": word_info.start_offset.total_seconds() if hasattr(word_info, 'start_offset') else 0.0,
                                "end_time": word_info.end_offset.total_seconds() if hasattr(word_info, 'end_offset') else 0.0,
                                "confidence": word_info.confidence if hasattr(word_info, 'confidence') else 0.0,
                            })
                    
                    # Handle based on is_final flag
                    if result.is_final:
                        # Final result
                        session.result_handler.handle_final_result(
                            text=transcript,
                            confidence=confidence,
                            words=words
                        )
                        logger.debug(
                            f"Final result for {session_id}: "
                            f"{transcript[:50]}... (confidence: {confidence:.2f})"
                        )
                    else:
                        # Interim result
                        session.result_handler.handle_interim_result(
                            text=transcript,
                            confidence=confidence,
                            words=words
                        )
                        logger.debug(
                            f"Interim result for {session_id}: "
                            f"{transcript[:50]}..."
                        )
                
                # Check for errors in response
                if hasattr(response, 'error') and response.error:
                    logger.error(
                        f"Error in streaming response for {session_id}: "
                        f"{response.error}"
                    )
                    session.status = SessionStatus.ERROR
                    break
        
        except google_exceptions.GoogleAPICallError as e:
            logger.error(
                f"gRPC error in result listener for {session_id}: {e}"
            )
            try:
                session = self.get_session(session_id)
                session.status = SessionStatus.ERROR
            except SessionNotFoundError:
                pass  # Session already closed
        
        except Exception as e:
            logger.error(
                f"Unexpected error in result listener for {session_id}: {e}",
                exc_info=True
            )
            try:
                session = self.get_session(session_id)
                session.status = SessionStatus.ERROR
            except SessionNotFoundError:
                pass
        
        finally:
            logger.info(f"Result listener stopped for session {session_id}")
