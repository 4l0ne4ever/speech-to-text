"""
Phase 2 Week 3 Integration Test: Speech-to-Text Core

Tests the core transcription functionality with real Google Cloud API.
Requires:
- Google Cloud credentials configured
- GCS bucket accessible
- Test audio files uploaded to GCS
"""

import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.google_cloud.speech_to_text import SpeechToTextService, TranscriptionError
from src.google_cloud.gcs_storage import GCSStorage
from src.models import TranscriptionOptions
from config.google_cloud_config import (
    GCP_SERVICE_ACCOUNT_KEY,
    GCS_BUCKET_NAME,
)


def test_upload_audio_to_gcs():
    """Test 1: Upload a test audio file to GCS."""
    print("\n" + "="*60)
    print("TEST 1: Upload Test Audio to GCS")
    print("="*60)
    
    # Initialize GCS storage
    gcs = GCSStorage(
        bucket_name=GCS_BUCKET_NAME,
        credentials_path=GCP_SERVICE_ACCOUNT_KEY
    )
    
    # Find a test audio file from ./audio/ folder
    audio_dir = Path(__file__).parent.parent / "audio"
    audio_files = list(audio_dir.glob("*.mp3")) + list(audio_dir.glob("*.wav")) + list(audio_dir.glob("*.m4a"))
    
    if not audio_files:
        print("❌ No audio files found in audio/")
        print("   Please add at least one audio file (.mp3, .wav, or .m4a)")
        return None
    
    # Use first audio file (pick a smaller one for faster testing)
    audio_files_sorted = sorted(audio_files, key=lambda x: x.stat().st_size)
    test_audio = audio_files_sorted[0]
    print(f"Using audio file: {test_audio.name}")
    print(f"File size: {test_audio.stat().st_size / 1024:.1f} KB")
    
    # Upload to GCS
    presentation_id = f"test_phase2_{int(time.time())}"
    gcs_key = f"presentations/{presentation_id}/audio/{test_audio.name}"
    
    print(f"Uploading to: gs://{GCS_BUCKET_NAME}/{gcs_key}")
    
    try:
        result = gcs.upload_file(
            local_file_path=str(test_audio),
            gcs_key=gcs_key
        )
        if not result["success"]:
            print(f"❌ Upload failed: {result.get('error')}")
            return None
        
        gcs_uri = result["gcs_uri"]
        print(f"✅ Upload successful: {gcs_uri}")
        return gcs_uri, presentation_id
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


def test_transcribe_audio(gcs_uri: str, presentation_id: str):
    """Test 2: Transcribe the uploaded audio file."""
    print("\n" + "="*60)
    print("TEST 2: Transcribe Audio with Google Cloud Speech-to-Text")
    print("="*60)
    
    # Initialize service
    print("Initializing SpeechToTextService...")
    service = SpeechToTextService(credentials_path=GCP_SERVICE_ACCOUNT_KEY)
    
    # Configure options for Japanese
    options = TranscriptionOptions(
        language_code="ja-JP",
        model="chirp",
        enable_automatic_punctuation=True,
        enable_word_timestamps=True,
        enable_speaker_diarization=False,
    )
    
    print(f"\nTranscription options:")
    print(f"  Language: {options.language_code}")
    print(f"  Model: {options.model}")
    print(f"  Word timestamps: {options.enable_word_timestamps}")
    print(f"  Automatic punctuation: {options.enable_automatic_punctuation}")
    
    print(f"\nStarting transcription...")
    print(f"GCS URI: {gcs_uri}")
    print("(This will take some time, polling every 5 seconds...)")
    
    start_time = time.time()
    
    try:
        # Note: Using sync version for simple test
        import asyncio
        result = asyncio.run(service.transcribe_audio(
            gcs_uri=gcs_uri,
            presentation_id=presentation_id,
            options=options
        ))
        
        elapsed = time.time() - start_time
        
        print(f"\n✅ Transcription completed in {elapsed:.1f}s")
        print(f"\n{'='*60}")
        print("TRANSCRIPTION RESULT")
        print('='*60)
        print(f"Presentation ID: {result.presentation_id}")
        print(f"Language: {result.language}")
        print(f"Model: {result.model}")
        print(f"Duration: {result.duration_seconds:.1f}s")
        print(f"Word count: {result.word_count}")
        print(f"Confidence: {result.confidence:.2%}")
        print(f"Processing time: {result.processing_time_seconds:.1f}s")
        print(f"Operation ID: {result.operation_id}")
        
        if result.quality_flags:
            print(f"Quality flags: {', '.join(result.quality_flags)}")
        
        print(f"\n{'='*60}")
        print("TRANSCRIPT")
        print('='*60)
        print(result.transcript)
        
        # Show first 5 words with timestamps
        if result.words and len(result.words) > 0:
            print(f"\n{'='*60}")
            print("WORD-LEVEL TIMESTAMPS (first 5 words)")
            print('='*60)
            for i, word in enumerate(result.words[:5]):
                print(f"{i+1}. '{word.word}' [{word.start_time:.2f}s - {word.end_time:.2f}s] (confidence: {word.confidence:.2%})")
            
            if len(result.words) > 5:
                print(f"... and {len(result.words) - 5} more words")
        
        # Calculate cost
        cost_per_15s = 0.024  # Chirp model
        total_cost = (result.duration_seconds / 15) * cost_per_15s
        
        print(f"\n{'='*60}")
        print("COST ESTIMATION")
        print('='*60)
        print(f"Audio duration: {result.duration_seconds:.1f}s ({result.duration_seconds/60:.2f} minutes)")
        print(f"Estimated cost: ${total_cost:.4f}")
        
        # Performance metrics
        processing_ratio = (result.processing_time_seconds / result.duration_seconds) * 100
        print(f"\n{'='*60}")
        print("PERFORMANCE METRICS")
        print('='*60)
        print(f"Processing time: {result.processing_time_seconds:.1f}s")
        print(f"Audio duration: {result.duration_seconds:.1f}s")
        print(f"Processing ratio: {processing_ratio:.1f}% of audio duration")
        
        if processing_ratio < 30:
            print("✅ PASS: Processing time < 30% of audio duration")
        else:
            print("⚠️  WARNING: Processing time > 30% of audio duration")
        
        return result
        
    except TranscriptionError as e:
        print(f"\n❌ Transcription failed: {e}")
        return None
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_cleanup_gcs(gcs_uri: str, presentation_id: str):
    """Test 3: Cleanup test files from GCS."""
    print("\n" + "="*60)
    print("TEST 3: Cleanup GCS Files")
    print("="*60)
    
    gcs = GCSStorage(credentials_path=GCP_SERVICE_ACCOUNT_KEY)
    
    try:
        deleted_count = gcs.cleanup_presentation(presentation_id)
        print(f"✅ Cleanup successful: {deleted_count} files deleted")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print(" PHASE 2 WEEK 3 INTEGRATION TEST: Speech-to-Text Core")
    print("="*70)
    print("\nThis test will:")
    print("1. Upload a test audio file to GCS")
    print("2. Transcribe it using Google Cloud Speech-to-Text API")
    print("3. Display the results and metrics")
    print("4. Cleanup test files from GCS")
    print("\nNOTE: This test uses real Google Cloud APIs and will incur costs.")
    print("      Estimated cost: ~$0.01-0.05 per test run (depending on audio length)")
    
    # Check credentials
    if not os.path.exists(GCP_SERVICE_ACCOUNT_KEY):
        print(f"\n❌ ERROR: Service account key not found at {GCP_SERVICE_ACCOUNT_KEY}")
        print("   Please configure your Google Cloud credentials.")
        return
    
    print("\n✅ Credentials found")
    print(f"✅ GCS bucket: {GCS_BUCKET_NAME}")
    
    # Confirm to proceed
    print("\n" + "="*70)
    response = input("Proceed with test? (y/n): ")
    if response.lower() != 'y':
        print("Test cancelled.")
        return
    
    # Run tests
    upload_result = test_upload_audio_to_gcs()
    
    if upload_result:
        gcs_uri, presentation_id = upload_result
        
        # Transcribe
        transcription_result = test_transcribe_audio(gcs_uri, presentation_id)
        
        # Cleanup
        test_cleanup_gcs(gcs_uri, presentation_id)
        
        # Final summary
        print("\n" + "="*70)
        print(" TEST SUMMARY")
        print("="*70)
        
        if transcription_result:
            print("✅ All tests passed!")
            print(f"\nKey Results:")
            print(f"  - Word count: {transcription_result.word_count}")
            print(f"  - Confidence: {transcription_result.confidence:.2%}")
            print(f"  - Duration: {transcription_result.duration_seconds:.1f}s")
            print(f"  - Processing time: {transcription_result.processing_time_seconds:.1f}s")
            
            if transcription_result.confidence >= 0.9:
                print("\n✅ EXCELLENT: Confidence >= 90%")
            elif transcription_result.confidence >= 0.7:
                print("\n✅ GOOD: Confidence >= 70%")
            else:
                print("\n⚠️  LOW CONFIDENCE: May need audio quality improvement")
        else:
            print("❌ Tests failed")
    else:
        print("\n❌ Upload failed, skipping transcription test")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
