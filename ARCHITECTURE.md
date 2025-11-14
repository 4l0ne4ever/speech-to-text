# Speech-to-Text System Architecture

## 🎯 Tổng Quan

Hệ thống Speech-to-Text với khả năng upload audio/PDF slides lên S3, transcribe bằng AssemblyAI, và lưu trữ metadata + transcript trong database.

---

## 🏗️ Kiến Trúc

```
┌─────────────────┐
│   User Input    │
│  (Audio + PDF)  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│   PresentationManager       │ ← Main Orchestrator
│  - create_presentation()    │
│  - transcribe_presentation()│
└─────┬──────────┬────────────┘
      │          │
      ▼          ▼
┌──────────┐  ┌──────────────┐
│ S3Storage│  │  Database    │
│  (boto3) │  │  (JSON)      │
└─────┬────┘  └──────────────┘
      │
      ▼
┌───────────────────┐
│  AssemblyAI STT   │
│ (speech_to_text)  │
└───────────────────┘
```

---

## 📦 Core Components

### 1. **config.py** - Configuration

- AssemblyAI API Key
- AWS credentials (Access Key, Secret Key, Region, Bucket)
- Default language: `ja` (Japanese)
- S3 folder structure: `presentations/{id}/audio/` và `/slides/`

### 2. **models.py** - Data Models

**Enums:**

- `PresentationStatus`: PENDING, PROCESSING, COMPLETED, FAILED
- `FileType`: AUDIO, PDF, THUMBNAIL
- `UploadStatus`: UPLOADED, PROCESSING, FAILED

**Models:**

- `Presentation`: ID, title, description, language, duration, status
- `AudioFile`: S3 key, file info, format, duration
- `SlideFile`: S3 key, PDF info, page count
- `Transcript`: Text, language, confidence, word count
- `TranscriptSegment`: Speaker labels, timestamps, text

### 3. **s3_storage.py** - AWS S3 Manager

```python
class S3Storage:
    upload_file(local_path, s3_key)           # Upload lên S3
    download_file(s3_key, local_path)         # Download về local
    generate_presigned_url(s3_key, exp=3600) # Tạo URL tạm thời
    list_files(prefix)                         # List files
    delete_file(s3_key)                        # Xóa file
    file_exists(s3_key)                        # Check tồn tại
```

### 4. **database.py** - JSON Database

CRUD operations cho tất cả models:

- `create_presentation()`, `get_presentation_by_id()`
- `create_audio_file()`, `create_slide_file()`
- `create_transcript()`, `create_segment()`
- Auto-increment IDs, JSON serialization

### 5. **speech_to_text.py** - AssemblyAI Integration

```python
class SpeechToText:
    transcribe_file(file_path, language)      # Transcribe local file
    transcribe_url(url, language)             # Transcribe từ URL
    transcribe_with_config(url, config)       # Custom config (speaker labels)
```

### 6. **presentation_manager.py** - Main Orchestrator

```python
class PresentationManager:
    create_presentation(audio_path, slide_path=None)  # Upload files
    transcribe_presentation(presentation_id)           # Transcribe
    get_presentation(presentation_id)                  # Get info
    list_presentations()                               # List all
    delete_presentation(presentation_id)               # Delete
```

---

## 🔄 Luồng Hoạt Động

### **1. Upload Files**

```
User → PresentationManager.create_presentation()
  ├─ Validate files tồn tại
  ├─ Generate presentation_id (pres_YYYYMMDD_xxxxxx)
  ├─ Upload audio → S3: presentations/{id}/audio/original.mp3
  ├─ Upload slide (optional) → S3: presentations/{id}/slides/original.pdf
  ├─ Save records → database.json
  └─ Return: presentation_id, audio_s3_key, slide_s3_key
```

### **2. Transcribe Audio**

```
PresentationManager.transcribe_presentation(id)
  ├─ Get presentation + audio_file từ database
  ├─ Update status → PROCESSING
  ├─ Generate presigned URL từ S3 (7200s expiration)
  ├─ Call AssemblyAI API
  │   └─ transcribe_url(presigned_url, language)
  ├─ Save transcript text → database
  ├─ Save segments (nếu có speaker labels) → database
  ├─ Update status → COMPLETED
  └─ Return: transcript, text, word_count, confidence
```

### **3. Retrieve Data**

```
PresentationManager.get_presentation(id)
  ├─ Get presentation from database
  ├─ Get audio_file, slide_file
  ├─ Get transcript + segments
  └─ Return: Full presentation data với relationships
```

---

## 🗄️ Data Storage

### **S3 Bucket Structure**

```
speed-to-text/
└── presentations/
    ├── pres_20251112_abc123/
    │   ├── audio/
    │   │   └── original.mp3
    │   └── slides/
    │       └── original.pdf
    └── pres_20251112_def456/
        └── audio/
            └── original.mp3
```

### **Database Structure (database.json)**

```json
{
  "presentations": [
    {
      "id": 1,
      "presentation_id": "pres_20251112_abc123",
      "title": "My Presentation",
      "language": "ja",
      "status": "completed",
      "created_at": "2025-11-12T10:00:00"
    }
  ],
  "audio_files": [
    {
      "id": 1,
      "presentation_id": 1,
      "s3_key": "presentations/pres_20251112_abc123/audio/original.mp3",
      "file_name": "audio.mp3",
      "file_size": 1024000
    }
  ],
  "transcripts": [
    {
      "id": 1,
      "audio_file_id": 1,
      "presentation_id": 1,
      "text": "Transcript text here...",
      "confidence": 0.95,
      "word_count": 150
    }
  ]
}
```

---

## 🚀 Usage Example

### **main.py** - Simple Test Flow

```python
from presentation_manager import PresentationManager

manager = PresentationManager()

# 1. Upload audio (+ optional PDF)
result = manager.create_presentation(
    audio_file_path="data/audio.mp3",
    slide_file_path=None,  # Optional
    title="Test Presentation",
    language="ja"
)

# 2. Transcribe
transcript = manager.transcribe_presentation(result["presentation_id"])

# 3. Get full data
presentation = manager.get_presentation(result["presentation_id"])
```

---

## 🔑 Key Features

✅ **Audio-only upload** - Slide PDF là optional  
✅ **Presigned URLs** - Không cần download file, transcribe trực tiếp từ S3  
✅ **Multi-language** - Hỗ trợ ja, en, vi, zh, ko, etc.  
✅ **Speaker labels** - Phân biệt người nói (optional)  
✅ **JSON Database** - Simple, không cần setup DB server  
✅ **S3 Backup** - Audio/PDF lưu trên cloud, transcript trong DB

---

## 📝 Environment Variables

```env
# AssemblyAI
ASSEMBLYAI_API_KEY=your_api_key_here

# AWS S3
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=ap-southeast-1
S3_BUCKET_NAME=speed-to-text

# Local
DOWNLOAD_FOLDER=./downloads
```

---

## 🔧 Dependencies

```
assemblyai==0.46.0
boto3==1.40.71
python-dotenv==1.0.1
```

---

## 🎤 AssemblyAI Integration

### **API Overview**

Hệ thống sử dụng **AssemblyAI Python SDK v0.46.0** để thực hiện speech-to-text transcription.

### **Configuration**

```python
# config.py
ASSEMBLYAI_API_KEY = "your_api_key"
DEFAULT_LANGUAGE = "ja"  # Japanese
DEFAULT_CONFIG = {
    "language_code": "ja",
    "punctuate": True,        # Tự động thêm dấu câu
    "format_text": True,      # Format text (capitalize, etc.)
}
```

### **Supported Languages**

AssemblyAI hỗ trợ 99+ ngôn ngữ, bao gồm:

- `ja` - Japanese (Tiếng Nhật)
- `en` - English
- `vi` - Vietnamese (Tiếng Việt)
- `zh` - Chinese (Tiếng Trung)
- `ko` - Korean (Tiếng Hàn)
- `es` - Spanish
- `fr` - French
- `de` - German
- Và nhiều ngôn ngữ khác...

### **Core Methods**

#### 1. **transcribe_file()** - Basic Transcription

```python
stt = SpeechToText()
result = stt.transcribe_file(
    audio_file_path="path/to/audio.mp3",
    language_code="ja"
)
# Returns: {success, text, confidence, audio_duration, language, words}
```

#### 2. **transcribe_url()** - Transcribe from URL

```python
# Dùng với S3 presigned URL
result = stt.transcribe_url(
    audio_url="https://s3.amazonaws.com/bucket/file.mp3?...",
    language_code="ja"
)
```

#### 3. **transcribe_with_config()** - Advanced Config

```python
result = stt.transcribe_with_config(
    audio_file_path="path/to/audio.mp3",
    language_code="ja",
    speaker_labels=True,          # Phân biệt người nói
    punctuate=True,
    format_text=True,
    language_detection=False      # Auto-detect language (nếu True)
)
# Returns: {success, text, confidence, speakers: [{speaker, text, start, end}]}
```

### **Features Được Sử Dụng**

✅ **Automatic Punctuation** - Tự động thêm dấu câu, dấu chấm, dấu phẩy  
✅ **Text Formatting** - Viết hoa chữ cái đầu câu, format text  
✅ **Multi-language** - Hỗ trợ transcribe nhiều ngôn ngữ  
✅ **Speaker Diarization** - Phân biệt người nói (A, B, C...)  
✅ **Confidence Score** - Độ chính xác của transcript (0.0 - 1.0)  
✅ **Word-level Timestamps** - Timestamp chi tiết từng từ  
✅ **URL-based Transcription** - Không cần download file

### **Workflow trong Hệ Thống**

```
1. PresentationManager.transcribe_presentation(id)
   ↓
2. Get audio S3 key from database
   ↓
3. Generate presigned URL (7200s expiration)
   ↓
4. SpeechToText.transcribe_url(presigned_url, language)
   ↓
5. AssemblyAI API Processing
   ↓
6. Return transcript + metadata
   ↓
7. Save to database.json
```

### **Error Handling**

```python
result = stt.transcribe_file("audio.mp3", "ja")

if not result["success"]:
    print(f"Error: {result['error']}")
else:
    print(f"Text: {result['text']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Duration: {result['audio_duration']}ms")
```

### **Response Structure**

```python
{
    "success": True,
    "text": "こんにちは。今日はいい天気ですね。",
    "confidence": 0.95,
    "audio_duration": 5000,  # milliseconds
    "language": "ja",
    "words": [...],          # Word-level details
    "speakers": [            # Nếu speaker_labels=True
        {
            "speaker": "A",
            "text": "こんにちは。",
            "start": 0,
            "end": 1500
        }
    ]
}
```

### **Pricing Note**

- AssemblyAI tính phí theo **giờ audio** được transcribe
- Free tier: 5 hours/month
- Paid: $0.00025/second (~$0.25/hour)
