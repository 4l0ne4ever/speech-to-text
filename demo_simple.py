#!/usr/bin/env python3
"""
Simple Real-Time Speech-to-Text Demo

Record from microphone and see transcription in real-time.
Uses Google Cloud Speech V2 API directly without custom session manager.

Requirements:
    pip install pyaudio google-cloud-speech

Usage:
    python demo_simple.py
"""

import os
import sys
import queue
import pyaudio
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms chunks
CHANNELS = 1
FORMAT = pyaudio.paInt16

# Colors
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
        """Continuously collect data from the audio stream."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        """Stream Audio from microphone"""
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Consume buffered data
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
    print(f"{BOLD}🎤 SIMPLE REAL-TIME SPEECH-TO-TEXT DEMO{RESET}")
    print("="*80)
    print(f"\n{YELLOW}Instructions:{RESET}")
    print(f"  • Speak Japanese into your microphone")
    print(f"  • {GRAY}Gray text{RESET} = Interim results (partial)")
    print(f"  • {GREEN}Green text{RESET} = Final results (confirmed)")
    print(f"  • Press {RED}Ctrl+C{RESET} to stop\n")
    print("="*80 + "\n")


def listen_print_loop(responses):
    """Iterates through server responses and prints them."""
    
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript

        if result.is_final:
            print(f"{GREEN}✓ {transcript}{RESET}")
        else:
            print(f"\r{GRAY}  {transcript}{RESET}", end='', flush=True)


def main():
    """Run simple streaming demo"""
    print_header()
    
    # Check credentials
    if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print(f"{RED}❌ Error: GOOGLE_APPLICATION_CREDENTIALS not set{RESET}\n")
        print("Run: ./run_demo.sh\n")
        sys.exit(1)
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT', 'speech-processing-prod')
    
    print(f"🔗 Connecting to Google Cloud Speech API...")
    print(f"   Project: {project_id}")
    print(f"   Model: latest_long (ja-JP)")
    print(f"   Sample Rate: {RATE} Hz\n")
    
    try:
        # Initialize client
        client = speech_v2.SpeechClient()
        
        # Build config
        recognition_config = cloud_speech.RecognitionConfig(
            explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
                encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=RATE,
                audio_channel_count=CHANNELS,
            ),
            language_codes=["ja-JP"],
            model="latest_long",
            features=cloud_speech.RecognitionFeatures(
                enable_automatic_punctuation=True,
                enable_word_time_offsets=False,
            ),
        )
        
        streaming_config = cloud_speech.StreamingRecognitionConfig(
            config=recognition_config,
            streaming_features=cloud_speech.StreamingRecognitionFeatures(
                interim_results=True
            ),
        )
        
        # Recognizer path
        recognizer = f"projects/{project_id}/locations/global/recognizers/_"
        
        # Request generator
        def request_generator(audio_generator):
            # First request with config
            yield cloud_speech.StreamingRecognizeRequest(
                recognizer=recognizer,
                streaming_config=streaming_config,
            )
            
            # Subsequent requests with audio
            for content in audio_generator:
                yield cloud_speech.StreamingRecognizeRequest(audio=content)
        
        print(f"{BOLD}🎙️  Recording... (speak now){RESET}\n")
        print("-"*80 + "\n")
        
        # Stream from microphone
        with MicrophoneStream(RATE, CHUNK) as stream:
            audio_generator = stream.generator()
            requests = request_generator(audio_generator)
            
            # Get responses
            responses = client.streaming_recognize(requests=requests)
            
            # Print results
            listen_print_loop(responses)
        
        print(f"\n\n{GREEN}✅ Demo completed!{RESET}\n")
        
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}⏹️  Stopped by user{RESET}")
        print(f"{GREEN}✅ Demo completed!{RESET}\n")
        
    except Exception as e:
        print(f"\n{RED}❌ Error: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
