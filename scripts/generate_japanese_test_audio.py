"""
Generate a short Japanese test audio file using Google Text-to-Speech
This will create a known-good audio file for testing transcription.
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import texttospeech
from config.google_cloud_config import GCP_SERVICE_ACCOUNT_KEY

def generate_test_audio():
    """Generate a 10-second Japanese test audio"""
    
    # Initialize TTS client
    client = texttospeech.TextToSpeechClient()
    
    # Japanese test text (~10 seconds of speech)
    test_text = """
    こんにちは。これはテストです。
    今日は良い天気ですね。
    音声認識のテストを行っています。
    """
    
    # Build synthesis input
    synthesis_input = texttospeech.SynthesisInput(text=test_text)
    
    # Build voice parameters (Japanese female voice)
    voice = texttospeech.VoiceSelectionParams(
        language_code="ja-JP",
        name="ja-JP-Standard-A",  # Female voice
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
    )
    
    # Build audio config (LINEAR16 for best quality)
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000
    )
    
    print("Generating Japanese test audio...")
    print(f"Text: {test_text.strip()}")
    
    # Perform TTS
    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )
    
    # Save to file
    output_dir = Path(__file__).parent.parent / "tests" / "test_data" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "test_japanese_short.wav"
    
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
    
    print(f"✅ Test audio generated: {output_file}")
    print(f"   Size: {len(response.audio_content)} bytes")
    print(f"   Format: LINEAR16 WAV, 16kHz")
    
    return output_file


if __name__ == "__main__":
    generate_test_audio()
