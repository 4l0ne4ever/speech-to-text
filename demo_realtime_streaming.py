#!/usr/bin/env python3
"""
Real-Time Speech-to-Text Demo

Record from microphone and see transcription in real-time.

Requirements:
    pip install pyaudio google-cloud-speech

Usage:
    python demo_realtime_streaming.py
    
    - Speak into your microphone
    - See interim results (gray) and final results (green)
    - Press Ctrl+C to stop
"""

import sys
import queue
import pyaudio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.streaming import (
    StreamingSessionManager,
    get_metrics_collector,
    AlertManager,
    AlertConfig,
)

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms chunks
CHANNELS = 1
FORMAT = pyaudio.paInt16

# Colors for terminal output
GRAY = '\033[90m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'


class MicrophoneStream:
    """Opens a recording stream as a generator yielding audio chunks."""
    
    def __init__(self, rate=RATE, chunk=CHUNK):
        self._rate = rate
        self._chunk = chunk
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio = pyaudio.PyAudio()
        self._stream = self._audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self._stream.stop_stream()
        self._stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """Stream Audio from microphone to API and to local buffer"""
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


def print_header():
    """Print demo header"""
    print("\n" + "="*80)
    print(f"{BOLD}🎤 REAL-TIME JAPANESE SPEECH-TO-TEXT DEMO{RESET}")
    print("="*80)
    print(f"\n{YELLOW}Instructions:{RESET}")
    print(f"  • Speak Japanese into your microphone")
    print(f"  • {GRAY}Gray text{RESET} = Interim results (partial, may change)")
    print(f"  • {GREEN}Green text{RESET} = Final results (confirmed)")
    print(f"  • Press {RED}Ctrl+C{RESET} to stop\n")
    print("="*80 + "\n")


def on_result(result):
    """Callback for streaming results"""
    if result.is_final:
        # Final result - print in green
        print(f"{GREEN}✓ {result.transcript}{RESET}")
    else:
        # Interim result - print in gray on same line
        print(f"\r{GRAY}  {result.transcript}{RESET}", end='', flush=True)


def on_alert(alert):
    """Callback for alerts"""
    if alert.severity.value == 'critical':
        print(f"\n{RED}🚨 ALERT: {alert.message}{RESET}")
    elif alert.severity.value == 'warning':
        print(f"\n{YELLOW}⚠️  WARNING: {alert.message}{RESET}")


def main():
    """Run real-time streaming demo"""
    print_header()
    
    # Check for Google Cloud credentials
    import os
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print(f"{RED}❌ Error: GOOGLE_APPLICATION_CREDENTIALS not set{RESET}\n")
        print("Please set your Google Cloud credentials:")
        print("  export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/credentials.json\n")
        sys.exit(1)
    
    # Get project ID
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print(f"{YELLOW}⚠️  GOOGLE_CLOUD_PROJECT not set, using default{RESET}")
        project_id = "your-project-id"
    
    print(f"🔗 Connecting to Google Cloud Speech API...")
    print(f"   Project: {project_id}")
    print(f"   Model: latest_long (ja-JP)")
    print(f"   Sample Rate: {RATE} Hz")
    print(f"   Chunk Size: {CHUNK} samples ({CHUNK/RATE*1000:.0f}ms)\n")
    
    try:
        # Initialize session manager with result callback
        session_manager = StreamingSessionManager(
            project_id=project_id,
            credentials_path=os.getenv('GOOGLE_APPLICATION_CREDENTIALS'),
            result_callback=on_result
        )
        
        # Setup monitoring
        metrics = get_metrics_collector()
        alert_config = AlertConfig(
            latency_p95_warning=800.0,
            latency_p95_critical=1500.0,
            error_rate_warning=5.0,
            error_rate_critical=10.0,
        )
        alert_manager = AlertManager(
            metrics_collector=metrics,
            config=alert_config,
            alert_callback=on_alert
        )
        alert_manager.start_monitoring()
        
        # Create session
        presentation_id = "live-demo"
        import uuid
        session_id = f"demo-{uuid.uuid4().hex[:8]}"
        
        print(f"📝 Creating streaming session...")
        session_manager.create_session(
            session_id=session_id,
            presentation_id=presentation_id
        )
        
        # Start session
        print(f"🚀 Starting speech recognition...\n")
        session_manager.start_session(
            session_id=session_id,
            language_code="ja-JP",
            model="latest_long",
            enable_interim_results=True
        )
        
        print(f"{BOLD}🎙️  Recording... (speak now){RESET}\n")
        print("-"*80 + "\n")
        
        # Stream from microphone
        with MicrophoneStream(RATE, CHUNK) as stream:
            audio_generator = stream.generator()
            
            try:
                for chunk in audio_generator:
                    if chunk:
                        # Send audio chunk to Google
                        session_manager.send_audio_chunk(session_id, chunk)
                        
            except KeyboardInterrupt:
                print(f"\n\n{YELLOW}⏹️  Stopping...{RESET}")
        
        # Stop session
        print(f"\n{BOLD}Finalizing session...{RESET}")
        summary = session_manager.stop_session(session_id)
        
        # Print statistics
        print("\n" + "="*80)
        print(f"{BOLD}📊 SESSION STATISTICS{RESET}")
        print("="*80)
        
        session_info = summary['session']
        audio_info = summary['audio_metrics']
        results_info = summary['results']
        
        print(f"\nSession:")
        print(f"  Duration: {session_info['duration']:.1f} seconds")
        print(f"  Chunks sent: {session_info['total_chunks_sent']}")
        print(f"  Bytes sent: {session_info['total_bytes_sent']:,}")
        
        print(f"\nAudio:")
        print(f"  Valid chunks: {audio_info['valid_chunks']}")
        print(f"  Invalid chunks: {audio_info['invalid_chunks']}")
        print(f"  Avg chunk size: {audio_info['avg_chunk_size']:.0f} bytes")
        
        print(f"\nResults:")
        print(f"  Interim results: {results_info['total_interim']}")
        print(f"  Final results: {results_info['total_final']}")
        if results_info['avg_confidence'] > 0:
            print(f"  Avg confidence: {results_info['avg_confidence']:.2%}")
        
        # Print metrics dashboard
        print("\n" + "="*80)
        print(metrics.get_dashboard_text())
        
        alert_manager.stop_monitoring()
        
        print(f"\n{GREEN}✅ Demo completed successfully!{RESET}\n")
        
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
