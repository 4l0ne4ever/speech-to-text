# Phase 2 Test Data Requirements

## Overview

This directory contains audio test samples for Phase 2 Speech-to-Text testing.

## Required Test Audio Files

### 1. Short Audio (< 1 minute)

**File:** `short_japanese_speech_30s.wav`

- **Duration:** 30 seconds
- **Purpose:** Quick validation, synchronous mode testing
- **Content:** Clear Japanese speech with simple vocabulary
- **Format:** WAV, 16kHz, mono, LINEAR16
- **Expected:** High confidence (>0.95), fast processing

### 2. Medium Audio (5-10 minutes)

**File:** `medium_presentation_8min.mp3`

- **Duration:** 8 minutes
- **Purpose:** Standard presentation processing
- **Content:** Japanese presentation with technical terms
- **Format:** MP3, 44.1kHz, stereo
- **Expected:** Normal processing, sentence segmentation

### 3. Long Audio (> 30 minutes)

**File:** `long_lecture_45min.m4a`

- **Duration:** 45 minutes
- **Purpose:** Long-running operation, pagination testing
- **Content:** Full Japanese lecture
- **Format:** M4A, 48kHz, stereo
- **Expected:** Handles long duration, proper pagination

### 4. Noisy Audio

**File:** `noisy_conference_room.wav`

- **Duration:** 5 minutes
- **Purpose:** Test noise handling and Google's noise cancellation
- **Content:** Japanese speech with background noise (people talking, AC, etc.)
- **Format:** WAV, 16kHz, mono
- **Expected:** Lower confidence but still transcribable

### 5. Multiple Format Tests

- `test_audio.mp3` - MP3 format
- `test_audio.wav` - WAV format
- `test_audio.m4a` - M4A format
- `test_audio.flac` - FLAC format

All should contain the same Japanese content for comparison.

### 6. Edge Cases

**Silent Audio:**

- `silent_10s.wav` - 10 seconds of silence
- **Expected:** Empty transcript or error handling

**Low Volume:**

- `low_volume_speech.wav` - Very quiet speech
- **Expected:** Preprocessing normalization, successful transcription

**Mixed Language:**

- `mixed_ja_en_speech.wav` - Japanese with English technical terms
- **Expected:** Handles code-switching, transcribes both languages

**Technical Vocabulary:**

- `technical_terms.wav` - Japanese speech with ML/AI terminology
- **Expected:** Correctly transcribes technical terms

## How to Add Test Files

### Option 1: Use Existing Audio

If you have actual Japanese presentation recordings:

```bash
# Copy to this directory
cp /path/to/your/audio.mp3 tests/test_data/audio/medium_presentation_8min.mp3
```

### Option 2: Generate Test Audio (for development)

For initial testing without real audio:

```python
# Use Google Cloud Text-to-Speech to generate test audio
# (Can be added as a utility script)

from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()

# Japanese text for testing
text = """
こんにちは。今日は機械学習について説明します。
機械学習は人工知能の一分野です。
データからパターンを学習することができます。
"""

synthesis_input = texttospeech.SynthesisInput(text=text)
voice = texttospeech.VoiceSelectionParams(
    language_code="ja-JP",
    name="ja-JP-Neural2-B"
)
audio_config = texttospeech.AudioConfig(
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    sample_rate_hertz=16000
)

response = client.synthesize_speech(
    input=synthesis_input,
    voice=voice,
    audio_config=audio_config
)

with open("short_japanese_speech_30s.wav", "wb") as out:
    out.write(response.audio_content)
```

### Option 3: Use Public Test Data

Japanese speech datasets:

- Common Voice (Mozilla) - https://commonvoice.mozilla.org/ja
- JVS (Japanese Versatile Speech) - https://sites.google.com/site/shinnosuketakamichi/research-topics/jvs_corpus
- JSUT (Japanese Single-speaker UTterance) - https://sites.google.com/site/shinnosuketakamichi/publication/jsut

## Ground Truth Transcripts

For accuracy testing, we need manual transcripts:

**Format:** `{audio_filename}.txt`

Example: `short_japanese_speech_30s.txt`

```
こんにちは。
今日は機械学習について説明します。
機械学習は人工知能の一分野です。
```

These will be used to calculate Word Error Rate (WER) and measure accuracy.

## Test Data Status

| File                          | Status       | Source | Notes                        |
| ----------------------------- | ------------ | ------ | ---------------------------- |
| short_japanese_speech_30s.wav | ❌ Not added | TBD    | Need to generate or source   |
| medium_presentation_8min.mp3  | ❌ Not added | TBD    | Prefer real presentation     |
| long_lecture_45min.m4a        | ❌ Not added | TBD    | Optional for initial testing |
| noisy_conference_room.wav     | ❌ Not added | TBD    | Can simulate noise           |
| Multiple format tests         | ❌ Not added | TBD    | Convert from one source      |
| Edge case samples             | ❌ Not added | TBD    | Generate programmatically    |

## Priority

**HIGH PRIORITY** (for Week 3 testing):

1. `short_japanese_speech_30s.wav` - Quick validation
2. `medium_presentation_8min.mp3` - Main test case

**MEDIUM PRIORITY** (for Week 4-5): 3. Multiple format tests 4. Noisy audio 5. Ground truth transcripts

**LOW PRIORITY** (optional): 6. Long audio (45 min) 7. Edge cases (can generate on demand)

## Notes

- All audio files should be added to `.gitignore` to avoid committing large files
- Consider using Git LFS if files need version control
- For CI/CD, use small test files or mock API responses
- Real audio preferred over synthetic for accuracy testing

---

**Next Step:** Add at least 2 audio files (short + medium) before starting Week 3 implementation.
