# Phase 2 Implementation Plan - Summary

## Status: Ready to Implement ✅

**Date:** November 13, 2025
**Phase:** Phase 2 - File-Based Processing Pipeline (Week 3-5)

---

## Architecture Review Complete ✅

### Key Understanding:

1. **Data Flow:**

   ```
   S3 Audio → S3-to-GCS Transfer (Phase 1) → Google Cloud Speech-to-Text API
   → Result Parsing → Transcript Segmentation → S3 Storage (JSON)
   ```

2. **Core Components:**

   - **SpeechToTextService:** Long-running recognition with Chirp model
   - **TranscriptProcessor:** Japanese sentence segmentation with punctuation
   - **AudioPreprocessor:** Format conversion using ffmpeg
   - **ResultStorage:** Atomic S3 writes with retry logic

3. **Critical Features:**

   - ✅ Word-level timestamps (essential for slide sync)
   - ✅ Japanese punctuation handling (。、？！)
   - ✅ Chirp model for best accuracy
   - ✅ Operation polling (5-10s intervals)
   - ✅ Error handling with exponential backoff

4. **Storage Schema:**
   ```
   presentations/{id}/transcripts/
     - transcript.json  (full transcript + segments)
     - words.json      (word-level details)
     - metadata.json   (processing info, cost)
   ```

---

## Test Data Preparation ✅

### Created:

- ✅ `tests/test_data/audio/` directory
- ✅ `tests/test_data/audio/README.md` - Requirements documentation
- ✅ `scripts/generate_test_audio.py` - TTS generator script

### Test Audio Categories:

1. **Short (30s):** Quick validation, high confidence
2. **Medium (5-8min):** Main test case, normal segmentation
3. **Long (45min):** Optional, for long-running ops
4. **Noisy:** Noise handling test
5. **Multi-format:** MP3, WAV, M4A, FLAC
6. **Edge cases:** Silent, low volume, mixed language

### Priority:

- **HIGH:** Short + Medium audio (for Week 3)
- **MEDIUM:** Multi-format, noisy (for Week 4-5)
- **LOW:** Long audio, edge cases (optional)

---

## Next Actions

### Before Implementation:

1. **Generate Test Audio** (Optional - can use TTS):

   ```bash
   python3 scripts/generate_test_audio.py
   ```

   Or add real Japanese presentation audio to `tests/test_data/audio/`

2. **Install Dependencies:**
   ```bash
   pip install pydub==0.25.1 ffmpeg-python==0.2.0
   brew install ffmpeg  # macOS
   ```

### Week 3: Core Implementation (3-5 days)

**Day 1-2: SpeechToTextService**

- Create `src/google_cloud/speech_to_text.py`
- Implement configuration builder (Chirp, ja-JP, word timestamps)
- Implement long-running recognition with operation polling
- Add comprehensive error handling

**Day 3-4: Result Parsing**

- Parse Google Cloud response structure
- Extract transcript, words, confidence scores
- Handle pagination for long audio
- Implement retry logic with exponential backoff

**Day 5: Unit Tests**

- Create `tests/test_speech_to_text.py`
- Mock API responses
- Test configuration builder
- Test error handling

### Week 4: Result Processing (3-5 days)

**Day 1-2: TranscriptProcessor**

- Create `src/processing/transcript_processor.py`
- Implement Japanese sentence segmentation
- Calculate segment timings from word timestamps
- Average confidence scores per segment

**Day 3-4: Result Storage**

- Create `src/aws/result_storage.py`
- Implement S3 storage structure
- Atomic write operations with retry
- JSON serialization with schemas

**Day 5: Unit Tests**

- Create `tests/test_transcript_processor.py`
- Test segmentation logic
- Test timing calculations
- Test storage operations

### Week 5: QA and Integration (3-5 days)

**Day 1-2: Audio Preprocessing**

- Create `src/processing/audio_preprocessor.py`
- Format detection and conversion
- Implement ffmpeg wrapper
- Volume normalization

**Day 3-4: Integration Tests**

- Create `tests/test_phase2_integration.py`
- End-to-end processing tests
- Test with real audio samples
- Test error recovery

**Day 5: Documentation and Metrics**

- Measure accuracy (WER) against ground truth
- Benchmark processing time
- Document cost per transcription
- Create PHASE2_COMPLETE.md

---

## Success Criteria Checklist

### Accuracy:

- [ ] Word accuracy > 90% for clear Japanese audio
- [ ] Timestamp accuracy within ±100ms
- [ ] Confidence scores correlate with actual accuracy

### Performance:

- [ ] Processing time < 30% of audio duration
- [ ] 95%+ success rate for valid audio files
- [ ] Auto-handle 5+ audio formats

### Reliability:

- [ ] Automatic retry succeeds on transient failures
- [ ] Error recovery without human intervention
- [ ] All processing metrics logged

### Deliverables:

- [ ] Core components implemented and tested
- [ ] Unit tests with >80% coverage
- [ ] Integration tests passing
- [ ] Documentation complete
- [ ] Cost tracking implemented

---

## Implementation Order (Recommended)

### Option 1: Bottom-up (Recommended for understanding)

1. AudioPreprocessor (format handling)
2. SpeechToTextService (core API)
3. TranscriptProcessor (segmentation)
4. ResultStorage (S3 operations)
5. Integration (end-to-end)

### Option 2: Top-down (Faster to working prototype)

1. SpeechToTextService with minimal config
2. Basic result parsing
3. Simple storage (no segmentation yet)
4. Add preprocessing and segmentation
5. Refine and test

### Recommendation: Start with Option 2

- Get working end-to-end quickly
- Test with real Google Cloud API early
- Discover issues sooner
- Refactor and add features incrementally

---

## Questions to Address During Implementation

1. **Operation Polling:**

   - What's optimal polling interval? (Plan says 5-10s)
   - Should we use exponential backoff for polling?
   - Max timeout before giving up?

2. **Segmentation:**

   - Should we combine short segments (<2s)?
   - How to handle segments without punctuation?
   - What confidence threshold triggers warning?

3. **Cost Tracking:**

   - How to estimate cost before processing?
   - Should we have cost limits per presentation?
   - Track cost in metadata.json or separate?

4. **Error Recovery:**
   - Should we retry immediately or queue for later?
   - How many retry attempts? (Plan suggests 3)
   - Notify user on persistent failures?

---

## Dependencies Review

### Already Installed (Phase 1):

- ✅ google-cloud-speech==2.21.0
- ✅ google-cloud-storage==2.10.0
- ✅ boto3==1.40.71

### Need to Install:

- ⏳ pydub==0.25.1
- ⏳ ffmpeg-python==0.2.0
- ⏳ ffmpeg (system package)

### Optional:

- MeCab (Japanese tokenizer) - for advanced segmentation
- janome (pure Python alternative) - easier to install

---

## Risk Assessment

### Low Risk:

- ✅ Google Cloud API integration (well-documented)
- ✅ S3 storage (already working in Phase 1)
- ✅ Basic transcription (straightforward API)

### Medium Risk:

- ⚠️ Japanese segmentation (language-specific, need testing)
- ⚠️ Audio format handling (many formats, ffmpeg complexity)
- ⚠️ Cost control (need monitoring to avoid overruns)

### High Risk:

- 🔴 Accuracy measurement (need ground truth data)
- 🔴 Long audio handling (pagination, splitting, merging)
- 🔴 Edge case coverage (many unknowns until tested)

### Mitigation:

1. Start with simple cases (short, clear audio)
2. Add complexity incrementally
3. Test early and often with real data
4. Monitor costs closely during development
5. Use staging environment with quota limits

---

## Estimated Timeline

**Optimistic:** 10 days (2 weeks)
**Realistic:** 15 days (3 weeks) ← Plan estimate
**Conservative:** 20 days (4 weeks)

**Critical Path:**

1. Get basic transcription working (Days 1-3)
2. Add segmentation (Days 4-5)
3. Polish and test (Days 6-10)
4. Edge cases and optimization (Days 11-15)

---

## Ready to Start? ✅

**Prerequisites Complete:**

- ✅ Architecture understood
- ✅ Test data structure prepared
- ✅ Documentation created
- ✅ Implementation plan clear

**Next Step Options:**

### Option A: Generate Test Audio First

```bash
python3 scripts/generate_test_audio.py
```

Then review generated files before implementing.

### Option B: Start Implementation Immediately

Begin with SpeechToTextService skeleton and mock tests.
Add real audio later during integration phase.

### Option C: Add Real Audio First

If you have real Japanese presentation recordings, add them to `tests/test_data/audio/` now for more realistic testing.

---

**Recommendation:** Start with Option B (implement with mocks), then add Option A (generate TTS audio) for quick validation, finally add Option C (real audio) for production testing.

---

**Status:** ✅ Analysis complete. Ready to implement Phase 2.

**Command to user:** "Sẵn sàng implement Phase 2. Bạn muốn tôi bắt đầu với component nào trước? (SpeechToTextService, AudioPreprocessor, hay generate test audio trước?)"
