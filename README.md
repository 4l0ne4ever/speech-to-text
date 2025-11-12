# Speech-to-Text với AssemblyAI

Dự án này sử dụng AssemblyAI API để chuyển đổi giọng nói thành văn bản.

## Cài đặt

1. **Cài đặt dependencies:**

```bash
pip install -r requirements.txt
```

2. **Cấu hình API Key:**
   - Tạo tài khoản tại [AssemblyAI](https://www.assemblyai.com/)
   - Lấy API key từ dashboard
   - Thêm API key vào file `.env`:

```
ASSEMBLYAI_API_KEY=your_api_key_here
```

## Cấu trúc dự án

```
speech_to_text/
├── __init__.py
├── config.py           # Cấu hình và load API key
├── speech_to_text.py   # Class chính xử lý speech-to-text
├── main.py            # Script demo
├── requirements.txt    # Dependencies
└── README.md          # Tài liệu này
```

## Sử dụng

### Cơ bản

```python
from speech_to_text import SpeechToText

# Khởi tạo
stt = SpeechToText()

# Transcribe từ URL
result = stt.transcribe_url("https://example.com/audio.mp3")

# Transcribe từ file local
result = stt.transcribe_file("path/to/audio.mp3")

if result["success"]:
    print(result["text"])
```

### Nâng cao - Với speaker detection

```python
result = stt.transcribe_with_config(
    "audio.mp3",
    speaker_labels=True,  # Phát hiện người nói
    language_code="vi"    # Ngôn ngữ tiếng Việt
)

if result["success"]:
    for utterance in result["speakers"]:
        print(f"Speaker {utterance['speaker']}: {utterance['text']}")
```

### Chạy demo

```bash
python main.py
```

## Tính năng

- ✅ Transcribe audio từ URL
- ✅ Transcribe audio từ file local
- ✅ Speaker diarization (phân biệt người nói)
- ✅ Hỗ trợ nhiều ngôn ngữ
- ✅ Confidence score
- ✅ Word-level timestamps

## Các tùy chọn config

```python
stt.transcribe_with_config(
    audio_file,
    speaker_labels=True,           # Phát hiện người nói
    language_code="vi",            # Ngôn ngữ
    punctuate=True,                # Thêm dấu câu
    format_text=True,              # Format text
    dual_channel=False,            # Audio 2 kênh
    sentiment_analysis=True,       # Phân tích cảm xúc
    auto_chapters=True,            # Tự động chia chương
    entity_detection=True,         # Phát hiện thực thể
    content_safety=True,           # Kiểm tra nội dung
)
```

## Định dạng audio được hỗ trợ

- MP3
- WAV
- FLAC
- OGG
- M4A
- WebM
- và nhiều định dạng khác...

## Giới hạn

- File audio tối đa: 5GB
- Free tier: 5 giờ transcription/tháng
- Paid plans: Unlimited

## Tài liệu tham khảo

- [AssemblyAI Docs](https://www.assemblyai.com/docs)
- [Python SDK](https://github.com/AssemblyAI/assemblyai-python-sdk)
