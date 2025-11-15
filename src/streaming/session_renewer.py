"""
Session Renewal Manager for Long-Running Streaming Sessions.

Handles:
- Monitoring session duration
- Triggering renewal at 4.5 minutes
- Seamless transition without dropping audio
- Buffering during renewal
- Logging renewal events
"""

import logging
import time
import threading
import queue
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class RenewalStatus(Enum):
    """Renewal operation status."""
    IDLE = "idle"
    PREPARING = "preparing"
    IN_PROGRESS = "in_progress"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RenewalEvent:
    """Record of a session renewal event."""
    session_id: str
    old_session_start: float
    old_session_duration: float
    new_session_start: float
    renewal_trigger_time: float
    renewal_complete_time: float
    buffered_chunks_count: int
    status: RenewalStatus
    error_message: Optional[str] = None
    
    def renewal_duration(self) -> float:
        """Get duration of renewal process in seconds."""
        return self.renewal_complete_time - self.renewal_trigger_time
    
    def to_dict(self) -> dict:
        """Export event details."""
        return {
            "session_id": self.session_id,
            "old_session_start": self.old_session_start,
            "old_session_duration": self.old_session_duration,
            "new_session_start": self.new_session_start,
            "renewal_trigger_time": self.renewal_trigger_time,
            "renewal_complete_time": self.renewal_complete_time,
            "renewal_duration": self.renewal_duration(),
            "buffered_chunks_count": self.buffered_chunks_count,
            "status": self.status.value,
            "error_message": self.error_message,
        }


@dataclass
class AudioBuffer:
    """Buffer for audio chunks during session renewal."""
    chunks: List[bytes] = field(default_factory=list)
    max_size: int = 50  # Maximum chunks to buffer
    total_bytes: int = 0
    
    def add(self, chunk: bytes) -> bool:
        """
        Add chunk to buffer.
        
        Args:
            chunk: Audio bytes
            
        Returns:
            True if added, False if buffer full
        """
        if len(self.chunks) >= self.max_size:
            logger.warning(
                f"Audio buffer full ({len(self.chunks)} chunks), "
                "dropping chunk"
            )
            return False
        
        self.chunks.append(chunk)
        self.total_bytes += len(chunk)
        return True
    
    def get_all(self) -> List[bytes]:
        """Get all buffered chunks and clear buffer."""
        chunks = self.chunks.copy()
        self.clear()
        return chunks
    
    def clear(self):
        """Clear all buffered chunks."""
        self.chunks.clear()
        self.total_bytes = 0
    
    def size(self) -> int:
        """Get number of buffered chunks."""
        return len(self.chunks)


class SessionRenewer:
    """
    Manages session renewal for long-running streaming sessions.
    
    Google Cloud streaming sessions timeout after:
    - ~5 minutes of continuous audio
    - ~1 minute of silence
    
    This class monitors session duration and triggers renewal at 4.5 minutes
    to prevent timeout, ensuring seamless continuation.
    """
    
    # Renewal threshold: 4.5 minutes = 270 seconds
    RENEWAL_THRESHOLD_SECONDS = 270.0
    
    # Grace period after renewal before allowing another
    RENEWAL_COOLDOWN_SECONDS = 10.0
    
    def __init__(
        self,
        session_manager,
        renewal_callback: Optional[Callable] = None
    ):
        """
        Initialize session renewer.
        
        Args:
            session_manager: StreamingSessionManager instance
            renewal_callback: Optional callback when renewal occurs
        """
        self.session_manager = session_manager
        self.renewal_callback = renewal_callback
        
        # Track renewal events
        self.renewal_history: List[RenewalEvent] = []
        
        # Audio buffer for renewal transition
        self.audio_buffers: Dict[str, AudioBuffer] = {}
        
        # Monitor thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitor = threading.Event()
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        logger.info("SessionRenewer initialized")
    
    def start_monitoring(self):
        """Start background thread to monitor sessions."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Monitor thread already running")
            return
        
        self.stop_monitor.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        
        logger.info("Session renewal monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring thread."""
        if not self.monitor_thread:
            return
        
        self.stop_monitor.set()
        self.monitor_thread.join(timeout=5.0)
        
        logger.info("Session renewal monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        logger.info("Monitor loop started")
        
        while not self.stop_monitor.is_set():
            try:
                # Check all active sessions
                active_sessions = self.session_manager.get_active_sessions()
                
                for session_id, session in active_sessions.items():
                    # Check if renewal needed
                    if self._should_renew(session):
                        logger.info(
                            f"Session {session_id} needs renewal "
                            f"(duration: {session.duration():.1f}s)"
                        )
                        
                        # Trigger renewal
                        self._renew_session(session_id, session)
                
                # Sleep before next check
                time.sleep(1.0)
            
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(5.0)  # Longer sleep on error
        
        logger.info("Monitor loop stopped")
    
    def _should_renew(self, session) -> bool:
        """
        Check if session should be renewed.
        
        Args:
            session: StreamingSession object
            
        Returns:
            True if renewal needed
        """
        # Must be active
        if session.status.value != "active":
            return False
        
        # Check duration threshold
        if session.duration() < self.RENEWAL_THRESHOLD_SECONDS:
            return False
        
        # Check cooldown period (prevent rapid renewals)
        if session.renewal_count > 0:
            # Check last renewal event
            for event in reversed(self.renewal_history):
                if event.session_id == session.session_id:
                    time_since_renewal = time.time() - event.new_session_start
                    if time_since_renewal < self.RENEWAL_COOLDOWN_SECONDS:
                        return False
                    break
        
        return True
    
    def _renew_session(self, session_id: str, session):
        """
        Renew a streaming session.
        
        Process:
        1. Create audio buffer for incoming chunks
        2. Close old session gracefully
        3. Wait for all results to arrive
        4. Open new session with same config
        5. Send buffered chunks to new session
        6. Resume normal operation
        
        Args:
            session_id: Session identifier
            session: StreamingSession object
        """
        with self.lock:
            renewal_start = time.time()
            
            logger.info(
                f"Starting renewal for session {session_id} "
                f"(duration: {session.duration():.1f}s, "
                f"renewal #{session.renewal_count + 1})"
            )
            
            # Create renewal event
            event = RenewalEvent(
                session_id=session_id,
                old_session_start=session.created_at,
                old_session_duration=session.duration(),
                new_session_start=0.0,  # Will be set later
                renewal_trigger_time=renewal_start,
                renewal_complete_time=0.0,  # Will be set later
                buffered_chunks_count=0,
                status=RenewalStatus.PREPARING
            )
            
            try:
                # Step 1: Create audio buffer
                buffer = AudioBuffer(max_size=50)
                self.audio_buffers[session_id] = buffer
                event.status = RenewalStatus.IN_PROGRESS
                
                logger.debug(f"Audio buffer created for {session_id}")
                
                # Step 2: Close old session
                # Note: During closing, incoming chunks will be buffered
                old_session_summary = self.session_manager.close_session(
                    session_id
                )
                
                logger.info(
                    f"Old session closed: {session_id} "
                    f"({old_session_summary['session']['total_chunks_sent']} chunks)"
                )
                
                # Step 3: Wait briefly for final results
                time.sleep(0.5)  # 500ms grace period
                
                # Step 4: Create new session with same config
                new_session = self.session_manager.create_session(
                    session_id=session_id,
                    presentation_id=session.presentation_id,
                )
                
                # Start new session
                self.session_manager.start_session(
                    session_id=session_id,
                    language_code="ja-JP",
                    model="latest_long",
                    enable_interim_results=True
                )
                
                event.new_session_start = time.time()
                new_session.renewal_count = session.renewal_count + 1
                
                logger.info(
                    f"New session started: {session_id} "
                    f"(renewal #{new_session.renewal_count})"
                )
                
                # Step 5: Send buffered chunks
                buffered_chunks = buffer.get_all()
                event.buffered_chunks_count = len(buffered_chunks)
                
                if buffered_chunks:
                    logger.info(
                        f"Sending {len(buffered_chunks)} buffered chunks "
                        f"to new session {session_id}"
                    )
                    
                    for chunk in buffered_chunks:
                        self.session_manager.send_audio_chunk(
                            session_id, chunk
                        )
                
                # Step 6: Clean up buffer
                del self.audio_buffers[session_id]
                
                # Mark completion
                event.renewal_complete_time = time.time()
                event.status = RenewalStatus.COMPLETED
                
                logger.info(
                    f"Session renewal completed: {session_id} "
                    f"(took {event.renewal_duration():.2f}s, "
                    f"buffered {event.buffered_chunks_count} chunks)"
                )
                
                # Invoke callback
                if self.renewal_callback:
                    try:
                        self.renewal_callback(event)
                    except Exception as e:
                        logger.error(
                            f"Error in renewal callback: {e}",
                            exc_info=True
                        )
            
            except Exception as e:
                event.status = RenewalStatus.FAILED
                event.error_message = str(e)
                event.renewal_complete_time = time.time()
                
                logger.error(
                    f"Session renewal failed for {session_id}: {e}",
                    exc_info=True
                )
                
                # Clean up buffer on error
                if session_id in self.audio_buffers:
                    del self.audio_buffers[session_id]
            
            finally:
                # Record event
                self.renewal_history.append(event)
    
    def buffer_audio_chunk(self, session_id: str, chunk: bytes) -> bool:
        """
        Buffer audio chunk during renewal.
        
        This is called by the session manager when a session is being renewed
        and cannot accept new chunks temporarily.
        
        Args:
            session_id: Session identifier
            chunk: Audio bytes
            
        Returns:
            True if buffered, False if no buffer exists
        """
        buffer = self.audio_buffers.get(session_id)
        if not buffer:
            return False
        
        return buffer.add(chunk)
    
    def is_renewing(self, session_id: str) -> bool:
        """Check if session is currently renewing."""
        return session_id in self.audio_buffers
    
    def get_renewal_history(
        self,
        session_id: Optional[str] = None
    ) -> List[RenewalEvent]:
        """
        Get renewal history.
        
        Args:
            session_id: Optional filter by session
            
        Returns:
            List of renewal events
        """
        if session_id:
            return [
                e for e in self.renewal_history
                if e.session_id == session_id
            ]
        return self.renewal_history.copy()
    
    def get_renewal_stats(self) -> dict:
        """Get renewal statistics."""
        if not self.renewal_history:
            return {
                "total_renewals": 0,
                "successful_renewals": 0,
                "failed_renewals": 0,
                "avg_renewal_duration": 0.0,
                "avg_buffered_chunks": 0.0,
            }
        
        successful = [
            e for e in self.renewal_history
            if e.status == RenewalStatus.COMPLETED
        ]
        failed = [
            e for e in self.renewal_history
            if e.status == RenewalStatus.FAILED
        ]
        
        return {
            "total_renewals": len(self.renewal_history),
            "successful_renewals": len(successful),
            "failed_renewals": len(failed),
            "avg_renewal_duration": (
                sum(e.renewal_duration() for e in successful) / len(successful)
                if successful else 0.0
            ),
            "avg_buffered_chunks": (
                sum(e.buffered_chunks_count for e in successful) / len(successful)
                if successful else 0.0
            ),
        }
