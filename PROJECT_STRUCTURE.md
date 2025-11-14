# Project Structure

## Overview

```
speech_to_text/
├── config/                          # Configuration files
│   ├── google_cloud_config.py      # Google Cloud settings (NEW)
│   └── legacy_config.py            # Old AssemblyAI config
│
├── src/                            # Source code
│   ├── google_cloud/               # Google Cloud integration (Phase 1 & 2)
│   │   ├── gcs_storage.py         # GCS operations wrapper
│   │   ├── speech_to_text.py      # Speech-to-Text service (Phase 2)
│   │   ├── result_storage.py      # GCS result storage (Phase 2)
│   │   └── __init__.py
│   │
│   ├── processing/                 # Processing pipeline (Phase 2)
│   │   ├── transcript_processor.py # Japanese segmentation
│   │   └── __init__.py
│   │
│   ├── legacy/                     # Legacy AssemblyAI code
│   │   ├── speech_to_text_assemblyai.py
│   │   ├── presentation_manager_assemblyai.py
│   │   ├── main_assemblyai.py
│   │   └── __init__.py
│   │
│   ├── models.py                   # Data models
│   ├── database.py                 # JSON database
│   └── __init__.py
│
├── tests/                          # Test suite
│   └── test_phase1_integration.py # Phase 1 integration tests
│
├── docs/                           # Documentation
│   ├── PHASE1_COMPLETE.md         # Phase 1 summary
│   └── phase1_setup.md            # Setup guide
│
├── data/                           # Test data
│
├── .env                            # Environment variables (not in git)
├── .env.example                    # Environment template
├── .gitignore
├── requirements.txt                # Python dependencies
├── ARCHITECTURE.md                 # System architecture
├── plan.md                         # Implementation plan
├── insight.md                      # Technical insights
└── README.md                       # This file
```

## Directory Descriptions

### `/config/`

Configuration files for different environments and services.

- **`google_cloud_config.py`**: Google Cloud Platform settings (GCP project, credentials, Speech-to-Text, Translation APIs)
- **`legacy_config.py`**: Old AssemblyAI configuration (will be deprecated)

### `/src/`

Main source code directory, organized by functionality.

#### `/src/google_cloud/`

**Phase 1** - Google Cloud integration components.

- **`gcs_storage.py`**: Google Cloud Storage wrapper

  - Upload/download files
  - File management (list, delete, cleanup)
  - Signed URL generation
  - Error handling and retry logic

- **`speech_to_text.py`**: Speech-to-Text service using Google Cloud API

  - Chirp model for Japanese transcription
  - Long-running recognition with operation polling
  - Word-level timestamps and confidence scores
  - Cost estimation

- **`result_storage.py`**: GCS result storage for transcriptions
  - Atomic JSON file writes (transcript, words, metadata)
  - Retry logic for reliability
  - Structured storage paths

#### `/src/processing/`

**Phase 2** - Transcript processing pipeline.

- **`transcript_processor.py`**: Japanese text segmentation
  - Sentence boundary detection using Japanese punctuation
  - Word-to-segment alignment
  - Confidence score aggregation
- Streaming recognition (Phase 3)
- PDF processing and slide matching (Phase 4)

#### `/src/legacy/`

Legacy code using AssemblyAI (kept for reference).

- **`speech_to_text_assemblyai.py`**: Old STT implementation
- **`presentation_manager_assemblyai.py`**: Old manager
- **`main_assemblyai.py`**: Old entry point

#### `/src/` (root level)

Shared modules.

- **`models.py`**: Data models (Presentation, AudioFile, TranscriptionResult, etc.)
- **`database.py`**: JSON database implementation

### `/tests/`

Test suite for all components.

- **`test_phase1_integration.py`**: GCS storage integration tests
- **`test_phase2_week3_integration.py`**: Speech-to-Text transcription tests
- **`test_phase2_week4_integration.py`**: Result processing and storage tests
- **`test_speech_to_text.py`**: Unit tests for Speech-to-Text service

### `/docs/`

Documentation and guides.

- **`PHASE1_COMPLETE.md`**: Phase 1 implementation summary
- **`phase1_setup.md`**: Step-by-step setup guide for Google Cloud

## Development Phases

### ✅ Phase 1: Foundation and Setup (Week 1-2) - COMPLETE

- Google Cloud Platform setup
- GCS storage wrapper
- Integration tests

### ✅ Phase 2: File-Based Processing (Week 3-4) - COMPLETE

- Google Cloud Speech-to-Text integration (Week 3)
  - Chirp model with Japanese support
  - Long-running recognition
  - Word-level timestamps
- Result processing and storage (Week 4)
  - Japanese text segmentation
  - GCS result storage
  - JSON output format

### 🔄 Phase 2: Week 5 - QA and Edge Cases (Optional)

- Audio preprocessing (format conversion)
- Edge case handling
- Comprehensive testing

### 🔜 Phase 3: Streaming Pipeline (Week 6-7)

- Real-time streaming recognition
- Session management
- Optimization

### 🔜 Phase 4: PDF & Slide Matching (Week 8-10)

- PDF text extraction
- Japanese tokenization
- Keyword indexing
- Slide-transcript matching algorithm

## Quick Start

1. **Install dependencies**:

```bash
pip install -r requirements.txt
```

2. **Setup Google Cloud** (see `docs/phase1_setup.md`):

   - Create GCP project
   - Enable APIs
   - Create service account
   - Download JSON key
   - Create GCS bucket

3. **Configure environment**:

```bash
cp .env.example .env
# Edit .env with your credentials
```

4. **Run Phase 1 tests**:

```bash
python3 tests/test_phase1_integration.py
```

## Key Files

- **`plan.md`**: Complete implementation plan for all 4 phases
- **`insight.md`**: Technical insights and architecture decisions
- **`ARCHITECTURE.md`**: System architecture documentation
- **`requirements.txt`**: Python package dependencies

## Migration Status

### ✅ Completed

- Project restructure
- Phase 1 implementation (GCS + transfer)
- Integration tests
- Documentation

### 🔄 In Progress

- Phase 2: Google Cloud Speech-to-Text

### 📋 Pending

- Migrate remaining legacy code
- Update ARCHITECTURE.md for Google Cloud
- Phase 3 & 4 implementation
