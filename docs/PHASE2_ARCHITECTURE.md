# Phase 2: File-Based Processing Pipeline - Architecture

## Overview

Phase 2 builds the complete processing pipeline for pre-recorded audio files using Google Cloud Speech-to-Text API with focus on Japanese language transcription.

**Timeline:** Week 3-5 (3 weeks)
**Status:** Planning and preparation

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Phase 2 Pipeline                         │
└─────────────────────────────────────────────────────────────────┘

┌──────────┐     ┌──────────┐     ┌──────────────┐     ┌──────────┐
│ S3 Audio │────▶│ S3→GCS   │────▶│ Audio Format │────▶│   GCS    │
│  Files   │     │ Transfer │     │ Validation   │     │  Bucket  │
└──────────┘     └──────────┘     └──────────────┘     └──────────┘
                       │                                      │
                       │ (Phase 1 complete)                  │
                       ▼                                      ▼
              ┌─────────────────┐              ┌──────────────────────┐
              │  Presentation   │              │ Google Cloud Speech  │
              │   Metadata      │              │  Long-running API    │
              │   (JSON DB)     │              │  (Chirp Model)       │
              └─────────────────┘              └──────────────────────┘
                                                          │
                                                          │ Poll every 5-10s
                                                          ▼
                                               ┌─────────────────────┐
                                               │ Operation Results   │
                                               │ - Full transcript   │
                                               │ - Word timestamps   │
                                               │ - Confidence scores │
                                               └─────────────────────┘
                                                          │
                ┌─────────────────────────────────────────┤
                │                                         │
                ▼                                         ▼
    ┌────────────────────────┐             ┌──────────────────────┐
    │ Transcript Processor   │             │  Result Storage      │
    │ - Sentence segmenting  │             │  (S3 Structure)      │
    │ - Japanese punctuation │             │  presentations/      │
    │ - Timestamp alignment  │             │    {id}/             │
    │ - Confidence calc      │             │      transcripts/    │
    └────────────────────────┘             │        transcript.json│
                │                           │        words.json    │
                │                           │        metadata.json │
                ▼                           └──────────────────────┘
    ┌────────────────────────┐
    │ Quality Validation     │
    │ - Check confidence     │
    │ - Verify completeness  │
    │ - Flag low quality     │
    └────────────────────────┘
                │
                ▼
    ┌────────────────────────┐
    │ API Response           │
    │ - Transcript object    │
    │ - Processing metadata  │
    │ - S3 result paths      │
    └────────────────────────┘
```

---

## Week 3: Google Cloud Speech-to-Text Integration

### Components

#### 1. **SpeechToTextService** (`src/google_cloud/speech_to_text.py`)

**Purpose:** Core service for transcription using Google Cloud Speech-to-Text API

**Key Methods:**

```python
async def transcribe_audio(
    gcs_uri: str,
    language_code: str = "ja-JP",
    options: TranscriptionOptions = None
) -> TranscriptionResult
```

**Configuration Builder:**

- Model: `chirp` (best accuracy for Japanese)
- Language: `ja-JP`
- Features:
  - Enable automatic punctuation (。、？！)
  - Enable word-level timestamps (CRITICAL for slide sync)
  - Optional speaker diarization (for Q&A sessions)
- Audio encoding: LINEAR16 (or auto-detect)
- Sample rate: 16000 Hz minimum, 48000 Hz ideal

**Processing Flow:**

1. Validate GCS URI exists and is accessible
2. Build RecognitionConfig with optimal settings
3. Submit LongRunningRecognize request
4. Store operation ID in database for tracking
5. Poll operation status every 5-10 seconds
6. On completion, parse and return results
7. On error, implement retry with exponential backoff

**Error Handling:**

- `AudioFormatError`: Unsupported format → trigger audio conversion
- `AudioTooLongError`: File > 480 minutes → auto-split into chunks
- `RateLimitError`: Quota exceeded → exponential backoff retry
- `TranscriptionError`: Generic failures → log and retry (max 3 attempts)

#### 2. **Audio Preprocessing** (`src/processing/audio_preprocessor.py`)

**Purpose:** Convert and optimize audio files for Google Cloud API

**Key Methods:**

```python
def detect_audio_format(file_path: str) -> AudioFormat
def convert_to_linear16(input_path: str, output_path: str) -> str
def normalize_volume(file_path: str) -> str
def remove_silence(file_path: str, threshold_db: int = -40) -> str
```

**Conversions:**

- MP3 → LINEAR16 WAV (16kHz mono)
- M4A → LINEAR16 WAV (16kHz mono)
- Any format → LINEAR16 WAV using ffmpeg

**Dependencies:** ffmpeg, pydub

---

## Week 4: Result Processing and Storage

### Components

#### 3. **TranscriptProcessor** (`src/processing/transcript_processor.py`)

**Purpose:** Process raw Google Cloud results into structured segments

**Key Methods:**

```python
def segment_by_sentences(
    transcript: str,
    words: List[WordInfo]
) -> List[TranscriptSegment]

def calculate_segment_timings(
    segment_text: str,
    words: List[WordInfo]
) -> Tuple[float, float, float]
```

**Segmentation Logic:**

- Japanese punctuation marks:
  - Period: 。 (U+3002)
  - Question: ？ (U+FF1F)
  - Exclamation: ！ (U+FF01)
  - Comma: 、 (U+3001) - for pauses, not segment boundaries
- Each segment includes:
  - `segment_id`: Unique identifier
  - `text`: Segment text
  - `start_time`: From first word start
  - `end_time`: From last word end
  - `confidence`: Average of word confidences
  - `word_count`: Number of words in segment

**Advanced Segmentation (Future):**

- Semantic grouping (5-second window)
- Topic modeling for paragraph boundaries
- Speaker change detection (if diarization enabled)

#### 4. **Result Storage** (`src/aws/result_storage.py`)

**Purpose:** Store processed transcription results in S3

**S3 Structure:**

```
presentations/
  {presentation_id}/
    transcripts/
      transcript.json       # Full transcript + metadata
      words.json           # Word-level details (large file)
      speakers.json        # Speaker diarization (if enabled)
      metadata.json        # Processing metadata
```

**File Schemas:**

**transcript.json:**

```json
{
  "presentation_id": "pres_20251113_abc123",
  "language": "ja-JP",
  "model": "chirp",
  "transcript": {
    "full_text": "こんにちは。今日は機械学習について説明します。",
    "confidence": 0.95,
    "duration_seconds": 1800.5,
    "word_count": 2500
  },
  "segments": [
    {
      "segment_id": "seg_001",
      "text": "こんにちは。",
      "start_time": 0.0,
      "end_time": 1.2,
      "confidence": 0.98,
      "word_count": 1
    }
  ],
  "processing": {
    "processed_at": "2025-11-13T10:30:00Z",
    "processing_duration_seconds": 180.5,
    "gcs_uri": "gs://speech-processing-intermediate/..."
  }
}
```

**words.json:**

```json
{
  "presentation_id": "pres_20251113_abc123",
  "words": [
    {
      "word": "こんにちは",
      "start_time": 0.0,
      "end_time": 1.2,
      "confidence": 0.98
    },
    {
      "word": "今日",
      "start_time": 2.0,
      "end_time": 2.5,
      "confidence": 0.96
    }
  ],
  "total_words": 2500
}
```

**metadata.json:**

```json
{
  "presentation_id": "pres_20251113_abc123",
  "processing": {
    "started_at": "2025-11-13T10:27:00Z",
    "completed_at": "2025-11-13T10:30:00Z",
    "duration_seconds": 180.5,
    "status": "completed"
  },
  "audio": {
    "duration_seconds": 1800.5,
    "format": "mp3",
    "sample_rate": 48000,
    "channels": 2,
    "size_bytes": 15728640
  },
  "google_cloud": {
    "operation_id": "1234567890",
    "model": "chirp",
    "language": "ja-JP",
    "features": {
      "automatic_punctuation": true,
      "word_timestamps": true,
      "speaker_diarization": false
    }
  },
  "quality": {
    "overall_confidence": 0.95,
    "low_confidence_segments": 12,
    "flags": []
  },
  "cost": {
    "processing_minutes": 30.01,
    "estimated_cost_usd": 2.88
  }
}
```

**Atomic Write Operations:**

1. Write to temporary file: `transcript.json.tmp`
2. Upload to S3 with retry logic
3. Verify upload (size check or checksum)
4. Rename from `.tmp` to final name
5. Clean up temporary files

---

## Week 5: Quality Assurance and Edge Cases

### Test Strategy

#### Test Data Categories

**1. Short Audio (< 1 minute):**

- Purpose: Test synchronous mode (if implemented) or quick validation
- File: `tests/test_data/audio/short_japanese_speech_30s.wav`
- Expected: Fast processing, high confidence

**2. Medium Audio (5-10 minutes):**

- Purpose: Standard presentation processing
- File: `tests/test_data/audio/medium_presentation_8min.mp3`
- Expected: Normal processing, typical segmentation

**3. Long Audio (> 30 minutes):**

- Purpose: Long-running operation testing
- File: `tests/test_data/audio/long_lecture_45min.m4a`
- Expected: Pagination handling, session management

**4. Noisy Audio:**

- Purpose: Test noise handling
- File: `tests/test_data/audio/noisy_conference_room.wav`
- Expected: Lower confidence, but still transcribable

**5. Multiple Formats:**

- Files: `.mp3`, `.wav`, `.m4a`, `.flac`
- Expected: All successfully converted and processed

**6. Edge Cases:**

- Silent audio (all zeros)
- Very low volume audio
- Corrupted audio file
- Audio with long silence periods
- Technical Japanese vocabulary
- Mixed language (Japanese + English terms)

#### Test Suites

**Unit Tests:**

- `tests/test_speech_to_text.py`
  - Test configuration builder
  - Test result parsing
  - Mock API responses
- `tests/test_transcript_processor.py`

  - Test sentence segmentation
  - Test timing calculation
  - Test confidence averaging

- `tests/test_audio_preprocessor.py`
  - Test format detection
  - Test conversion functions
  - Test preprocessing pipeline

**Integration Tests:**

- `tests/test_phase2_integration.py`
  - Test end-to-end processing
  - Test with real audio samples
  - Test error recovery
  - Test result storage

### Edge Case Handling

**Empty/Silent Audio:**

```python
if len(results) == 0 or transcript_text.strip() == "":
    return TranscriptionResult(
        transcript="",
        confidence=0.0,
        duration=audio_duration,
        segments=[],
        status="empty_audio"
    )
```

**Low Confidence Results:**

```python
if overall_confidence < 0.5:
    metadata["quality_flags"].append("low_confidence")
    # Optionally trigger reprocessing with different model
```

**API Timeout:**

```python
if operation_time > MAX_OPERATION_TIME:
    # Split audio file into chunks
    chunks = split_audio_file(audio_file, chunk_duration=30*60)
    results = []
    for chunk in chunks:
        result = await transcribe_audio(chunk)
        results.append(result)
    return merge_results(results)
```

---

## Success Metrics

### Accuracy

- ✅ Word accuracy > 90% for clear Japanese audio (measured against manual transcripts)
- ✅ Timestamp accuracy within ±100ms
- ✅ Confidence scores correlate with actual accuracy

### Performance

- ✅ Processing time < 30% of audio duration (60min audio → <18min processing)
- ✅ 95%+ success rate for valid audio files
- ✅ Auto-handle 5+ audio formats without manual intervention

### Reliability

- ✅ Automatic retry succeeds on transient failures
- ✅ Error recovery without human intervention
- ✅ All processing metrics logged

### Cost

- ✅ Cost tracking per transcription
- ✅ Cost estimates match actuals within 10%
- ✅ Optimization opportunities identified

---

## Phase 2 Deliverables

1. **Code Components:**

   - ✅ `src/google_cloud/speech_to_text.py` - Core transcription service
   - ✅ `src/processing/transcript_processor.py` - Segmentation and formatting
   - ✅ `src/processing/audio_preprocessor.py` - Audio conversion and preprocessing
   - ✅ `src/aws/result_storage.py` - S3 result storage with atomic writes

2. **Configuration:**

   - ✅ Updated `config/google_cloud_config.py` with Speech-to-Text settings
   - ✅ Environment variables documented

3. **Tests:**

   - ✅ Unit tests for all components
   - ✅ Integration tests with real audio samples
   - ✅ Edge case tests
   - ✅ Performance benchmarks

4. **Documentation:**

   - ✅ API specifications
   - ✅ Configuration options guide
   - ✅ S3 storage schema documentation
   - ✅ Error codes and handling procedures
   - ✅ Performance benchmarks

5. **Test Data:**
   - ✅ Diverse audio samples in `tests/test_data/audio/`
   - ✅ Ground truth transcripts for accuracy measurement
   - ✅ Test results and metrics

---

## Dependencies

### Python Packages (to be installed)

```
google-cloud-speech==2.21.0  # Already installed in Phase 1
pydub==0.25.1                 # Audio manipulation
ffmpeg-python==0.2.0          # FFmpeg wrapper
```

### System Dependencies

```bash
# Install FFmpeg (required for audio conversion)
brew install ffmpeg  # macOS
```

### Google Cloud APIs

- ✅ Speech-to-Text API (already enabled in Phase 1)
- ✅ Cloud Storage API (already enabled in Phase 1)

---

## Next Steps

1. **Immediate:**

   - Gather or create test audio samples
   - Set up test data directory structure
   - Install ffmpeg and pydub

2. **Week 3 Implementation:**

   - Build SpeechToTextService with configuration builder
   - Implement long-running recognition with polling
   - Add comprehensive error handling

3. **Week 4 Implementation:**

   - Build TranscriptProcessor with Japanese segmentation
   - Implement S3 result storage with atomic writes
   - Create JSON schemas

4. **Week 5 Testing:**
   - Run comprehensive test suite
   - Measure accuracy and performance
   - Document results and optimization opportunities

---

**Status:** Architecture reviewed and documented. Ready to proceed with implementation.
**Date:** November 13, 2025
