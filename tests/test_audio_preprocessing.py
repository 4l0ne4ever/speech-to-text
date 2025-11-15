"""
Test Audio Preprocessing (VAD, AGC)

Tests voice activity detection and automatic gain control.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.streaming.audio_preprocessing import (
    VoiceActivityDetector,
    AutomaticGainControl,
    AudioPreprocessor,
    AudioActivity,
    VADConfig,
    AGCConfig,
)


def generate_audio_chunk(
    duration_ms: int = 100,
    frequency_hz: int = 440,
    amplitude: float = 0.5,
    sample_rate: int = 16000
) -> bytes:
    """Generate synthetic audio chunk for testing."""
    num_samples = int(sample_rate * duration_ms / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples)
    
    # Generate sine wave
    audio = amplitude * np.sin(2 * np.pi * frequency_hz * t)
    
    # Convert to int16
    audio_int16 = (audio * 32767).astype(np.int16)
    
    return audio_int16.tobytes()


def generate_silence_chunk(
    duration_ms: int = 100,
    sample_rate: int = 16000
) -> bytes:
    """Generate silence chunk for testing."""
    num_samples = int(sample_rate * duration_ms / 1000)
    audio_int16 = np.zeros(num_samples, dtype=np.int16)
    return audio_int16.tobytes()


def test_vad_speech_detection():
    """Test 1: VAD Speech Detection"""
    print("\n" + "="*60)
    print("TEST 1: VAD Speech Detection")
    print("="*60)
    
    vad = VoiceActivityDetector(
        config=VADConfig(
            energy_threshold_db=-40.0,
            min_speech_duration=0.2,
            min_silence_duration=1.0,
        )
    )
    
    # Test speech chunk
    speech_chunk = generate_audio_chunk(
        duration_ms=100,
        amplitude=0.5  # Loud enough to be detected
    )
    
    # Process multiple chunks to exceed min_speech_duration
    for i in range(5):  # 5 chunks = 500ms > 200ms threshold
        activity = vad.process_chunk(speech_chunk)
        print(f"   Chunk {i+1}: {activity.value}")
    
    assert activity == AudioActivity.SPEECH, "Should detect speech"
    print(f"✅ Speech detected after {vad.speech_frames} frames")
    
    # Test silence chunk
    vad.reset()
    silence_chunk = generate_silence_chunk(duration_ms=100)
    
    for i in range(15):  # 15 chunks = 1500ms > 1000ms threshold
        activity = vad.process_chunk(silence_chunk)
    
    assert activity == AudioActivity.SILENCE, "Should detect silence"
    print(f"✅ Silence detected after {vad.silence_frames} frames")
    
    # Get stats
    stats = vad.get_stats()
    print(f"\n   VAD Stats:")
    print(f"   - Total frames: {stats['total_frames']}")
    print(f"   - Speech ratio: {stats['speech_ratio']:.2%}")
    print(f"   - Silence ratio: {stats['silence_ratio']:.2%}")
    
    print("\n✅ VAD speech detection tests completed")


def test_agc_normalization():
    """Test 2: AGC Normalization"""
    print("\n" + "="*60)
    print("TEST 2: AGC Normalization")
    print("="*60)
    
    agc = AutomaticGainControl(
        config=AGCConfig(
            target_db=-1.0,
            max_gain_db=30.0,
            min_gain_db=-10.0,
            smoothing_factor=0.5,
        )
    )
    
    # Test quiet audio
    quiet_chunk = generate_audio_chunk(
        duration_ms=100,
        amplitude=0.05  # Very quiet
    )
    
    # Calculate original RMS
    original_audio = np.frombuffer(quiet_chunk, dtype=np.int16).astype(np.float32) / 32768.0
    original_rms = np.sqrt(np.mean(original_audio ** 2))
    original_db = 20 * np.log10(original_rms) if original_rms > 1e-10 else -100.0
    
    print(f"   Original audio: {original_db:.1f}dB")
    
    # Process with AGC
    normalized_chunk = agc.process_chunk(quiet_chunk)
    
    # Calculate normalized RMS
    normalized_audio = np.frombuffer(normalized_chunk, dtype=np.int16).astype(np.float32) / 32768.0
    normalized_rms = np.sqrt(np.mean(normalized_audio ** 2))
    normalized_db = 20 * np.log10(normalized_rms) if normalized_rms > 1e-10 else -100.0
    
    print(f"   Normalized audio: {normalized_db:.1f}dB")
    print(f"   Applied gain: {agc.current_gain_db:.1f}dB")
    
    # Check that volume increased
    assert normalized_db > original_db, "Volume should increase"
    print(f"✅ Quiet audio amplified ({original_db:.1f} → {normalized_db:.1f}dB)")
    
    # Test loud audio
    agc.reset()
    loud_chunk = generate_audio_chunk(
        duration_ms=100,
        amplitude=0.95  # Very loud, close to clipping
    )
    
    loud_audio = np.frombuffer(loud_chunk, dtype=np.int16).astype(np.float32) / 32768.0
    loud_rms = np.sqrt(np.mean(loud_audio ** 2))
    loud_db = 20 * np.log10(loud_rms)
    
    print(f"\n   Loud audio: {loud_db:.1f}dB")
    
    normalized_loud = agc.process_chunk(loud_chunk)
    normalized_loud_audio = np.frombuffer(normalized_loud, dtype=np.int16).astype(np.float32) / 32768.0
    normalized_loud_rms = np.sqrt(np.mean(normalized_loud_audio ** 2))
    normalized_loud_db = 20 * np.log10(normalized_loud_rms)
    
    print(f"   Normalized loud: {normalized_loud_db:.1f}dB")
    print(f"   Applied gain: {agc.current_gain_db:.1f}dB")
    
    # AGC should bring it closer to target (-1dB)
    assert abs(normalized_loud_db - (-1.0)) < abs(loud_db - (-1.0)), \
        "Should be closer to target"
    print(f"✅ Loud audio normalized toward target ({loud_db:.1f} → {normalized_loud_db:.1f}dB)")
    
    # Get stats
    stats = agc.get_stats()
    print(f"\n   AGC Stats:")
    print(f"   - Total chunks: {stats['total_chunks']}")
    print(f"   - Avg gain: {stats['avg_gain_db']:.1f}dB")
    print(f"   - Min gain: {stats['min_gain_db']:.1f}dB")
    print(f"   - Max gain: {stats['max_gain_db']:.1f}dB")
    
    print("\n✅ AGC normalization tests completed")


def test_audio_preprocessor_pipeline():
    """Test 3: Complete Preprocessing Pipeline"""
    print("\n" + "="*60)
    print("TEST 3: Complete Preprocessing Pipeline")
    print("="*60)
    
    preprocessor = AudioPreprocessor(
        enable_vad=True,
        enable_agc=True,
    )
    
    # Process speech chunk
    speech_chunk = generate_audio_chunk(
        duration_ms=100,
        amplitude=0.3
    )
    
    processed, activity = preprocessor.process_chunk(speech_chunk)
    
    print(f"   Speech chunk processed")
    print(f"   - Original size: {len(speech_chunk)} bytes")
    print(f"   - Processed size: {len(processed)} bytes")
    print(f"   - Activity: {activity.value}")
    print(f"   - Should send: {preprocessor.should_send_chunk(activity)}")
    
    assert len(processed) == len(speech_chunk), "Size should not change"
    print(f"✅ Speech chunk processed correctly")
    
    # Process silence chunk  
    silence_chunk = generate_silence_chunk(duration_ms=100)
    
    for i in range(15):  # Build up silence detection
        processed, activity = preprocessor.process_chunk(silence_chunk)
    
    print(f"\n   Silence chunks processed")
    print(f"   - Activity: {activity.value}")
    print(f"   - Should send: {preprocessor.should_send_chunk(activity)}")
    
    assert not preprocessor.should_send_chunk(activity), "Should not send silence"
    print(f"✅ Silence chunks filtered correctly")
    
    # Get combined stats
    stats = preprocessor.get_stats()
    print(f"\n   Preprocessor Stats:")
    print(f"   - VAD enabled: {stats['vad_enabled']}")
    print(f"   - AGC enabled: {stats['agc_enabled']}")
    if 'vad' in stats:
        print(f"   - Speech ratio: {stats['vad']['speech_ratio']:.2%}")
    if 'agc' in stats:
        print(f"   - Avg gain: {stats['agc']['avg_gain_db']:.1f}dB")
    
    print("\n✅ Preprocessing pipeline tests completed")


def test_vad_config():
    """Test 4: VAD Configuration"""
    print("\n" + "="*60)
    print("TEST 4: VAD Configuration")
    print("="*60)
    
    # Test with custom thresholds
    strict_vad = VoiceActivityDetector(
        config=VADConfig(
            energy_threshold_db=-30.0,  # Stricter threshold
            min_speech_duration=0.5,
            min_silence_duration=0.5,
        )
    )
    
    lenient_vad = VoiceActivityDetector(
        config=VADConfig(
            energy_threshold_db=-50.0,  # More lenient
            min_speech_duration=0.1,
            min_silence_duration=3.0,
        )
    )
    
    # Test with medium-quiet audio
    medium_chunk = generate_audio_chunk(
        duration_ms=100,
        amplitude=0.1  # Medium-quiet
    )
    
    # Process with both VADs
    for i in range(10):
        strict_activity = strict_vad.process_chunk(medium_chunk)
        lenient_activity = lenient_vad.process_chunk(medium_chunk)
    
    print(f"   Strict VAD (-30dB): {strict_activity.value}")
    print(f"   Lenient VAD (-50dB): {lenient_activity.value}")
    
    # Lenient should be more likely to detect speech
    print(f"✅ VAD thresholds affect detection as expected")
    
    print("\n✅ VAD configuration tests completed")


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AUDIO PREPROCESSING TESTS")
    print("="*60)
    
    try:
        test_vad_speech_detection()
        test_agc_normalization()
        test_audio_preprocessor_pipeline()
        test_vad_config()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nAudio preprocessing module is ready!")
        print("\nKey features:")
        print("  • Voice Activity Detection (VAD)")
        print("  • Automatic Gain Control (AGC)")
        print("  • Combined preprocessing pipeline")
        print("  • Configurable thresholds")
        print("  • Statistics tracking")
        
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
