"""
Test Session Renewal Logic

Tests the automatic session renewal mechanism for long-running streaming sessions.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.streaming import (
    SessionRenewer,
    RenewalEvent,
    RenewalStatus,
    AudioBuffer,
)


def test_audio_buffer():
    """Test 1: Audio buffer during renewal"""
    print("\n" + "="*60)
    print("TEST 1: Audio Buffer")
    print("="*60)
    
    buffer = AudioBuffer(max_size=5)
    
    # Add chunks
    chunk1 = b'\x00' * 3200
    chunk2 = b'\x00' * 4800
    chunk3 = b'\x00' * 6400
    
    assert buffer.add(chunk1), "Should add chunk 1"
    assert buffer.add(chunk2), "Should add chunk 2"
    assert buffer.add(chunk3), "Should add chunk 3"
    
    print(f"✅ Added 3 chunks")
    print(f"   Buffer size: {buffer.size()}")
    print(f"   Total bytes: {buffer.total_bytes}")
    
    assert buffer.size() == 3
    assert buffer.total_bytes == 3200 + 4800 + 6400
    
    # Get all chunks
    chunks = buffer.get_all()
    assert len(chunks) == 3
    assert buffer.size() == 0  # Should be cleared
    print(f"✅ Retrieved all chunks, buffer cleared")
    
    # Test buffer overflow
    buffer = AudioBuffer(max_size=2)
    assert buffer.add(b'\x00' * 3200)
    assert buffer.add(b'\x00' * 3200)
    assert not buffer.add(b'\x00' * 3200), "Should reject when full"
    print(f"✅ Buffer overflow handled correctly")
    
    print("\n✅ Audio buffer tests completed")


def test_renewal_event():
    """Test 2: Renewal event tracking"""
    print("\n" + "="*60)
    print("TEST 2: Renewal Event")
    print("="*60)
    
    event = RenewalEvent(
        session_id="test-session-1",
        old_session_start=1000.0,
        old_session_duration=270.5,
        new_session_start=1270.5,
        renewal_trigger_time=1270.0,
        renewal_complete_time=1271.5,
        buffered_chunks_count=5,
        status=RenewalStatus.COMPLETED
    )
    
    assert event.renewal_duration() == 1.5
    print(f"✅ Renewal duration: {event.renewal_duration()}s")
    
    event_dict = event.to_dict()
    assert event_dict['session_id'] == "test-session-1"
    assert event_dict['buffered_chunks_count'] == 5
    assert event_dict['status'] == "completed"
    print(f"✅ Event export to dict works")
    
    print(f"\n   Event details:")
    print(f"   - Old session duration: {event.old_session_duration}s")
    print(f"   - Renewal duration: {event.renewal_duration()}s")
    print(f"   - Buffered chunks: {event.buffered_chunks_count}")
    print(f"   - Status: {event.status.value}")
    
    print("\n✅ Renewal event tests completed")


def test_session_renewer_basic():
    """Test 3: SessionRenewer basic functionality"""
    print("\n" + "="*60)
    print("TEST 3: SessionRenewer Basic")
    print("="*60)
    
    # Mock session manager
    class MockSessionManager:
        def __init__(self):
            self.sessions = {}
        
        def get_active_sessions(self):
            return self.sessions
        
        def create_session(self, session_id, presentation_id):
            class MockSession:
                def __init__(self):
                    self.session_id = session_id
                    self.presentation_id = presentation_id
                    self.created_at = time.time()
                    self.renewal_count = 0
                    self.status = type('obj', (object,), {'value': 'active'})()
                
                def duration(self):
                    return time.time() - self.created_at
            
            session = MockSession()
            self.sessions[session_id] = session
            return session
        
        def start_session(self, session_id, **kwargs):
            pass
        
        def close_session(self, session_id):
            if session_id in self.sessions:
                del self.sessions[session_id]
            return {
                'session': {'total_chunks_sent': 100},
                'results': {},
            }
        
        def send_audio_chunk(self, session_id, chunk):
            pass
    
    # Create renewer
    manager = MockSessionManager()
    renewer = SessionRenewer(session_manager=manager)
    
    print(f"✅ SessionRenewer created")
    
    # Test audio buffering
    session_id = "test-session-1"
    chunk = b'\x00' * 3200
    
    # Should return False (no buffer yet)
    assert not renewer.buffer_audio_chunk(session_id, chunk)
    print(f"✅ Buffer check before renewal: False (expected)")
    
    # Create buffer manually
    renewer.audio_buffers[session_id] = AudioBuffer()
    assert renewer.buffer_audio_chunk(session_id, chunk)
    print(f"✅ Buffered chunk successfully")
    
    # Check if renewing
    assert renewer.is_renewing(session_id)
    print(f"✅ is_renewing() returns True")
    
    # Get stats
    stats = renewer.get_renewal_stats()
    assert stats['total_renewals'] == 0
    print(f"✅ Initial stats: {stats['total_renewals']} renewals")
    
    print("\n✅ SessionRenewer basic tests completed")


def test_renewal_threshold():
    """Test 4: Renewal threshold logic"""
    print("\n" + "="*60)
    print("TEST 4: Renewal Threshold")
    print("="*60)
    
    # Create mock session
    class MockSession:
        def __init__(self, duration_seconds):
            self._duration = duration_seconds
            self.status = type('obj', (object,), {'value': 'active'})()
            self.renewal_count = 0
            self.session_id = "test-session"
        
        def duration(self):
            return self._duration
    
    # Mock manager
    class MockManager:
        def get_active_sessions(self):
            return {}
    
    renewer = SessionRenewer(session_manager=MockManager())
    
    # Test below threshold
    session_short = MockSession(duration_seconds=240.0)  # 4 minutes
    assert not renewer._should_renew(session_short)
    print(f"✅ Session at 4min: No renewal (< 4.5min threshold)")
    
    # Test at threshold
    session_ready = MockSession(duration_seconds=270.0)  # 4.5 minutes
    assert renewer._should_renew(session_ready)
    print(f"✅ Session at 4.5min: Renewal triggered")
    
    # Test above threshold
    session_late = MockSession(duration_seconds=280.0)  # 4.67 minutes
    assert renewer._should_renew(session_late)
    print(f"✅ Session at 4.67min: Renewal triggered")
    
    # Test inactive session
    session_inactive = MockSession(duration_seconds=280.0)
    session_inactive.status = type('obj', (object,), {'value': 'closing'})()
    assert not renewer._should_renew(session_inactive)
    print(f"✅ Inactive session: No renewal (status=closing)")
    
    print("\n✅ Renewal threshold tests completed")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("SESSION RENEWAL TESTS")
    print("="*60)
    
    try:
        test_audio_buffer()
        test_renewal_event()
        test_session_renewer_basic()
        test_renewal_threshold()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nSession renewal module is ready!")
        print("\nKey features:")
        print("  • Audio buffering during renewal")
        print("  • Renewal threshold at 4.5 minutes")
        print("  • Event tracking and statistics")
        print("  • Seamless session transition")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
