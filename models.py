from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum


class PresentationStatus(str, Enum):
    """Status của presentation"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileType(str, Enum):
    """Loại file"""
    AUDIO = "audio"
    PDF = "pdf"
    THUMBNAIL = "thumbnail"


class UploadStatus(str, Enum):
    """Upload status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    FAILED = "failed"


@dataclass
class Presentation:
    """Model cho presentation"""
    id: int
    presentation_id: str  # Business ID (pres_20241112_001)
    title: str
    description: Optional[str] = None
    language: str = "ja"
    duration: Optional[float] = None  # seconds
    status: PresentationStatus = PresentationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    user_id: Optional[int] = None


@dataclass
class AudioFile:
    """Model cho audio file"""
    id: int
    presentation_id: int  # FK
    s3_key: str
    s3_url: Optional[str] = None
    file_name: str = "original.mp3"
    file_size: int = 0  # bytes
    format: str = "mp3"
    duration: Optional[float] = None  # seconds
    upload_status: UploadStatus = UploadStatus.UPLOADED
    uploaded_at: datetime = field(default_factory=datetime.now)
    checksum: Optional[str] = None


@dataclass
class SlideFile:
    """Model cho slide PDF"""
    id: int
    presentation_id: int  # FK
    s3_key: str
    s3_url: Optional[str] = None
    file_name: str = "original.pdf"
    file_size: int = 0  # bytes
    page_count: Optional[int] = None
    upload_status: UploadStatus = UploadStatus.UPLOADED
    uploaded_at: datetime = field(default_factory=datetime.now)
    checksum: Optional[str] = None


@dataclass
class Transcript:
    """Model cho transcript"""
    id: int
    audio_file_id: int  # FK
    presentation_id: int  # FK (redundant nhưng tiện query)
    text: str
    language_detected: str = "ja"
    confidence: float = 0.0
    processing_status: str = "completed"
    processed_at: datetime = field(default_factory=datetime.now)
    word_count: int = 0


@dataclass
class TranscriptSegment:
    """Model cho transcript segment với timestamps"""
    id: int
    transcript_id: int  # FK
    text: str
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float = 0.0
    speaker_label: Optional[str] = None  # A, B, C...
    segment_order: int = 0
