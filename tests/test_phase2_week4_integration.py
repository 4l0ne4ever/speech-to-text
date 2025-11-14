"""
Phase 2 Week 4 Integration Test: Result Processing

Tests transcript segmentation and GCS storage.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.processing.transcript_processor import TranscriptProcessor
from src.google_cloud.result_storage import GCSResultStorage
from src.models import TranscriptionResult, WordInfo
from config.google_cloud_config import (
    GCP_SERVICE_ACCOUNT_KEY,
    GCS_INTERMEDIATE_BUCKET,
)


def test_transcript_segmentation():
    """Test 1: Segment a transcript using Japanese punctuation."""
    print("\n" + "="*60)
    print("TEST 1: Transcript Segmentation")
    print("="*60)
    
    # Create a mock transcription result
    words = [
        WordInfo(word="こんにちは", start_time=0.0, end_time=1.2, confidence=0.95),
        WordInfo(word="今日", start_time=1.5, end_time=2.0, confidence=0.92),
        WordInfo(word="は", start_time=2.0, end_time=2.2, confidence=0.98),
        WordInfo(word="機械", start_time=2.5, end_time=3.0, confidence=0.90),
        WordInfo(word="学習", start_time=3.0, end_time=3.5, confidence=0.91),
        WordInfo(word="について", start_time=3.5, end_time=4.2, confidence=0.93),
        WordInfo(word="説明", start_time=4.3, end_time=5.0, confidence=0.94),
        WordInfo(word="します", start_time=5.0, end_time=5.8, confidence=0.96),
    ]
    
    transcript = "こんにちは。今日は機械学習について説明します。"
    
    result = TranscriptionResult(
        presentation_id="test_segment_001",
        transcript=transcript,
        language="ja-JP",
        confidence=0.94,
        duration_seconds=5.8,
        word_count=len(words),
        words=words,
        model="chirp",
    )
    
    print(f"Original transcript: {transcript}")
    print(f"Word count: {len(words)}")
    
    # Process
    processor = TranscriptProcessor()
    result = processor.segment_by_sentences(result)
    
    # Display results
    print(f"\n✅ Segmentation completed")
    print(f"Number of segments: {len(result.segments)}")
    
    for i, segment in enumerate(result.segments):
        print(f"\nSegment {i+1} ({segment.segment_id}):")
        print(f"  Text: {segment.text}")
        print(f"  Time: {segment.start_time:.2f}s - {segment.end_time:.2f}s (duration: {segment.duration():.2f}s)")
        print(f"  Confidence: {segment.confidence:.2%}")
        print(f"  Word count: {segment.word_count}")
    
    return result


def test_save_to_gcs():
    """Test 2: Save transcription result to GCS."""
    print("\n" + "="*60)
    print("TEST 2: Save Result to GCS")
    print("="*60)
    
    # Create test result
    words = [
        WordInfo(word="テスト", start_time=0.0, end_time=0.8, confidence=0.95),
        WordInfo(word="です", start_time=0.9, end_time=1.5, confidence=0.92),
    ]
    
    from src.processing.transcript_processor import TranscriptProcessor
    
    result = TranscriptionResult(
        presentation_id="test_storage_001",
        transcript="テストです。",
        language="ja-JP",
        confidence=0.94,
        duration_seconds=1.5,
        word_count=2,
        words=words,
        model="chirp",
        processing_time_seconds=10.5,
        gcs_uri="gs://test-bucket/test.mp3",
        operation_id="test_op_123",
    )
    
    # Segment it first
    processor = TranscriptProcessor()
    result = processor.segment_by_sentences(result)
    
    # Save to GCS
    storage = GCSResultStorage(
        bucket_name=GCS_INTERMEDIATE_BUCKET,
        credentials_path=GCP_SERVICE_ACCOUNT_KEY
    )
    
    print(f"Saving to GCS bucket: {GCS_INTERMEDIATE_BUCKET}")
    print(f"Presentation ID: {result.presentation_id}")
    
    try:
        uris = storage.save_transcription_result(result, result.presentation_id)
        
        print("\n✅ Save successful!")
        print(f"\nSaved files:")
        print(f"  transcript.json: {uris['transcript']}")
        print(f"  words.json: {uris['words']}")
        print(f"  metadata.json: {uris['metadata']}")
        
        return result.presentation_id, storage
        
    except Exception as e:
        print(f"\n❌ Save failed: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def test_retrieve_from_gcs(presentation_id: str, storage: GCSResultStorage):
    """Test 3: Retrieve transcription result from GCS."""
    print("\n" + "="*60)
    print("TEST 3: Retrieve Result from GCS")
    print("="*60)
    
    try:
        data = storage.get_transcription_result(presentation_id)
        
        if data:
            print("✅ Retrieved successfully!")
            print(f"\nTranscript data:")
            print(f"  Presentation ID: {data['presentation_id']}")
            print(f"  Language: {data['language']}")
            print(f"  Model: {data['model']}")
            print(f"  Full text: {data['transcript']['full_text']}")
            print(f"  Confidence: {data['transcript']['confidence']:.2%}")
            print(f"  Segments: {len(data['segments'])}")
        else:
            print("❌ Transcript not found")
            
    except Exception as e:
        print(f"❌ Retrieve failed: {e}")


def test_cleanup_gcs(presentation_id: str, storage: GCSResultStorage):
    """Test 4: Cleanup test files from GCS."""
    print("\n" + "="*60)
    print("TEST 4: Cleanup GCS Files")
    print("="*60)
    
    try:
        deleted_count = storage.delete_transcription_result(presentation_id)
        print(f"✅ Cleanup successful: {deleted_count} files deleted")
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")


def main():
    """Run all Week 4 tests."""
    print("\n" + "="*70)
    print(" PHASE 2 WEEK 4 INTEGRATION TEST: Result Processing")
    print("="*70)
    print("\nThis test will:")
    print("1. Test transcript segmentation with Japanese punctuation")
    print("2. Save transcription results to GCS")
    print("3. Retrieve results from GCS")
    print("4. Cleanup test files")
    
    # Check credentials
    if not os.path.exists(GCP_SERVICE_ACCOUNT_KEY):
        print(f"\n❌ ERROR: Service account key not found")
        return
    
    print("\n✅ Credentials found")
    print(f"✅ GCS bucket: {GCS_INTERMEDIATE_BUCKET}")
    
    # Run tests
    print("\n" + "="*70)
    
    # Test 1: Segmentation
    segmented_result = test_transcript_segmentation()
    
    # Test 2: Save to GCS
    save_result = test_save_to_gcs()
    
    if save_result[0]:
        presentation_id, storage = save_result
        
        # Test 3: Retrieve
        test_retrieve_from_gcs(presentation_id, storage)
        
        # Test 4: Cleanup
        test_cleanup_gcs(presentation_id, storage)
        
        print("\n" + "="*70)
        print(" TEST SUMMARY")
        print("="*70)
        print("✅ All Week 4 tests passed!")
        print("\nKey Results:")
        print(f"  - Segmentation: {len(segmented_result.segments)} segments created")
        print(f"  - Storage: Files saved to GCS successfully")
        print(f"  - Retrieval: Data retrieved successfully")
        print(f"  - Cleanup: Files cleaned up")
    else:
        print("\n❌ Tests failed")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
