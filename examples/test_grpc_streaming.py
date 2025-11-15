"""
Test gRPC Streaming with Google Cloud Speech-to-Text V2 API

This example demonstrates:
1. Initialize streaming session with credentials
2. Send audio chunks in real-time
3. Receive interim and final results
4. Handle session lifecycle

Requirements:
- Google Cloud credentials JSON file
- GCP_PROJECT_ID environment variable
- Audio file in LINEAR16 format, 16kHz, mono
"""

import os
import sys
import time
import wave
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.streaming import StreamingSessionManager, StreamingResult


def simulate_streaming_from_file(
    audio_file_path: str,
    credentials_path: str,
    project_id: str,
    chunk_size: int = 3200  # 100ms at 16kHz
):
    """
    Simulate real-time streaming from an audio file.
    
    Args:
        audio_file_path: Path to WAV file (LINEAR16, 16kHz, mono)
        credentials_path: Path to GCP service account JSON
        project_id: GCP project ID
        chunk_size: Size of each audio chunk in bytes
    """
    
    print("="*60)
    print("Google Cloud Speech-to-Text V2 - Streaming Test")
    print("="*60)
    
    # Result callback
    def on_result(result: StreamingResult):
        result_type = "FINAL" if result.is_final else "INTERIM"
        print(f"\n[{result_type}] {result.text}")
        if result.is_final:
            print(f"         Confidence: {result.confidence:.2f}")
    
    # Initialize manager
    print(f"\n1. Initializing StreamingSessionManager...")
    print(f"   Project ID: {project_id}")
    print(f"   Credentials: {credentials_path}")
    
    try:
        manager = StreamingSessionManager(
            credentials_path=credentials_path,
            project_id=project_id,
            result_callback=on_result
        )
        print("   ✅ Manager initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize manager: {e}")
        return
    
    # Create session
    print(f"\n2. Creating streaming session...")
    session_id = f"test-session-{int(time.time())}"
    presentation_id = "test-presentation"
    
    try:
        session = manager.create_session(
            session_id=session_id,
            presentation_id=presentation_id
        )
        print(f"   ✅ Session created: {session_id}")
    except Exception as e:
        print(f"   ❌ Failed to create session: {e}")
        return
    
    # Start session (open gRPC stream)
    print(f"\n3. Starting session (opening gRPC stream)...")
    try:
        manager.start_session(
            session_id=session_id,
            language_code="ja-JP",
            model="latest_long",
            enable_interim_results=True
        )
        print("   ✅ Session started, gRPC stream open")
    except Exception as e:
        print(f"   ❌ Failed to start session: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Open audio file
    print(f"\n4. Opening audio file: {audio_file_path}")
    try:
        with wave.open(audio_file_path, 'rb') as wf:
            # Validate format
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            
            print(f"   Channels: {channels}")
            print(f"   Sample width: {sample_width} bytes")
            print(f"   Sample rate: {framerate} Hz")
            
            if channels != 1:
                print(f"   ⚠️  Warning: Expected mono (1 channel), got {channels}")
            if sample_width != 2:
                print(f"   ⚠️  Warning: Expected 16-bit (2 bytes), got {sample_width}")
            if framerate != 16000:
                print(f"   ⚠️  Warning: Expected 16kHz, got {framerate} Hz")
            
            # Calculate total duration
            n_frames = wf.getnframes()
            duration_sec = n_frames / framerate
            print(f"   Duration: {duration_sec:.1f} seconds")
            print(f"   Total frames: {n_frames}")
            
            # Stream audio
            print(f"\n5. Streaming audio chunks ({chunk_size} bytes each)...")
            chunk_count = 0
            start_time = time.time()
            
            while True:
                # Read chunk
                data = wf.readframes(chunk_size // (channels * sample_width))
                if not data:
                    break
                
                # Send chunk
                try:
                    success = manager.send_audio_chunk(
                        session_id=session_id,
                        chunk=data
                    )
                    
                    if success:
                        chunk_count += 1
                        
                        # Print progress every 10 chunks
                        if chunk_count % 10 == 0:
                            elapsed = time.time() - start_time
                            print(f"   Sent {chunk_count} chunks ({elapsed:.1f}s elapsed)")
                    else:
                        print(f"   ⚠️  Failed to send chunk {chunk_count + 1}")
                
                except Exception as e:
                    print(f"   ❌ Error sending chunk: {e}")
                    break
                
                # Simulate real-time by adding delay
                # chunk_duration = len(data) / (framerate * channels * sample_width)
                # time.sleep(chunk_duration)
                
                # For testing, send faster (no delay)
                time.sleep(0.01)
            
            elapsed = time.time() - start_time
            print(f"\n   ✅ Streaming complete: {chunk_count} chunks in {elapsed:.1f}s")
    
    except FileNotFoundError:
        print(f"   ❌ Audio file not found: {audio_file_path}")
        return
    except Exception as e:
        print(f"   ❌ Error reading audio file: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Wait for final results
    print(f"\n6. Waiting for final results...")
    time.sleep(3.0)
    
    # Close session
    print(f"\n7. Closing session...")
    try:
        summary = manager.close_session(session_id)
        
        print("   ✅ Session closed")
        print(f"\n   Session Summary:")
        print(f"   - Duration: {summary['session']['duration']:.1f}s")
        print(f"   - Chunks sent: {summary['session']['total_chunks_sent']}")
        print(f"   - Bytes sent: {summary['session']['total_bytes_sent']}")
        print(f"   - Final results: {summary['results']['total_final_results']}")
        print(f"   - Interim results: {summary['results']['total_interim_results']}")
        
        # Print full transcript
        full_transcript = summary['results']['full_transcript']
        print(f"\n   Full Transcript:")
        print(f"   {full_transcript}")
        
    except Exception as e:
        print(f"   ❌ Error closing session: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    
    # Get credentials from environment
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    project_id = os.getenv('GCP_PROJECT_ID')
    
    if not credentials_path:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS environment variable not set")
        print("   Export your service account JSON path:")
        print("   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json")
        sys.exit(1)
    
    if not project_id:
        print("❌ GCP_PROJECT_ID environment variable not set")
        print("   Export your GCP project ID:")
        print("   export GCP_PROJECT_ID=your-project-id")
        sys.exit(1)
    
    # Audio file path
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
    else:
        # Default test file
        audio_file = "test_audio_16khz_mono.wav"
    
    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        print("\nUsage: python test_grpc_streaming.py <audio_file.wav>")
        print("\nAudio requirements:")
        print("  - Format: WAV")
        print("  - Encoding: LINEAR16 (16-bit PCM)")
        print("  - Sample rate: 16kHz")
        print("  - Channels: Mono (1)")
        sys.exit(1)
    
    # Run test
    simulate_streaming_from_file(
        audio_file_path=audio_file,
        credentials_path=credentials_path,
        project_id=project_id,
        chunk_size=3200  # 100ms chunks
    )


if __name__ == "__main__":
    main()
