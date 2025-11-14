from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
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


class ProcessingStatus(Enum):
    """Status of a processing operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AudioFormat(Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    M4A = "m4a"
    FLAC = "flac"
    OGG = "ogg"
    LINEAR16 = "linear16"
    UNKNOWN = "unknown"


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


# ============================================================================
# Phase 2: New models for Speech-to-Text processing
# ============================================================================


@dataclass
class WordInfo:
    """Word-level timing and confidence information."""
    word: str
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float  # 0.0 to 1.0
    
    def duration(self) -> float:
        """Calculate word duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class TranscriptionSegment:
    """A segment of transcript with timing information (for Phase 2)."""
    segment_id: str
    text: str
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float  # 0.0 to 1.0
    word_count: int
    words: List[WordInfo] = field(default_factory=list)
    
    def duration(self) -> float:
        """Calculate segment duration in seconds."""
        return self.end_time - self.start_time


@dataclass
class SpeakerSegment:
    """Speaker diarization information."""
    speaker_label: str  # e.g., "Speaker A", "Speaker B"
    text: str
    start_time: float  # seconds
    end_time: float  # seconds
    confidence: float  # 0.0 to 1.0


@dataclass
class TranscriptionOptions:
    """Configuration options for transcription."""
    language_code: str = "ja-JP"
    model: str = "chirp"  # "chirp", "latest_long", "latest_short"
    enable_automatic_punctuation: bool = True
    enable_word_timestamps: bool = True
    enable_speaker_diarization: bool = False
    audio_encoding: Optional[str] = None  # None = auto-detect
    sample_rate_hertz: Optional[int] = None  # None = auto-detect
    max_alternatives: int = 1  # Number of alternative transcripts
    profanity_filter: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "language_code": self.language_code,
            "model": self.model,
            "enable_automatic_punctuation": self.enable_automatic_punctuation,
            "enable_word_timestamps": self.enable_word_timestamps,
            "enable_speaker_diarization": self.enable_speaker_diarization,
            "audio_encoding": self.audio_encoding,
            "sample_rate_hertz": self.sample_rate_hertz,
            "max_alternatives": self.max_alternatives,
            "profanity_filter": self.profanity_filter,
        }


@dataclass
class TranscriptionResult:
    """Complete transcription result."""
    presentation_id: str
    transcript: str  # Full transcript text
    language: str
    confidence: float  # Overall confidence 0.0 to 1.0
    duration_seconds: float
    word_count: int
    segments: List[TranscriptionSegment] = field(default_factory=list)
    words: List[WordInfo] = field(default_factory=list)
    speakers: List[SpeakerSegment] = field(default_factory=list)
    
    # Processing metadata
    model: str = "chirp"
    processing_time_seconds: Optional[float] = None
    gcs_uri: Optional[str] = None
    operation_id: Optional[str] = None
    
    # Quality flags
    has_low_confidence: bool = False
    low_confidence_threshold: float = 0.5
    quality_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "presentation_id": self.presentation_id,
            "transcript": self.transcript,
            "language": self.language,
            "confidence": self.confidence,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "segments": [
                {
                    "segment_id": seg.segment_id,
                    "text": seg.text,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "confidence": seg.confidence,
                    "word_count": seg.word_count,
                }
                for seg in self.segments
            ],
            "model": self.model,
            "processing_time_seconds": self.processing_time_seconds,
            "gcs_uri": self.gcs_uri,
            "operation_id": self.operation_id,
            "has_low_confidence": self.has_low_confidence,
            "quality_flags": self.quality_flags,
        }


@dataclass
class ProcessingMetadata:
    """Metadata about the processing operation."""
    presentation_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    status: ProcessingStatus = ProcessingStatus.PENDING
    
    # Audio information
    audio_duration_seconds: Optional[float] = None
    audio_format: Optional[str] = None
    audio_sample_rate: Optional[int] = None
    audio_channels: Optional[int] = None
    audio_size_bytes: Optional[int] = None
    
    # Google Cloud information
    operation_id: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    features: Dict[str, bool] = field(default_factory=dict)
    
    # Quality metrics
    overall_confidence: Optional[float] = None
    low_confidence_segments: int = 0
    quality_flags: List[str] = field(default_factory=list)
    
    # Cost estimation
    processing_minutes: Optional[float] = None
    estimated_cost_usd: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "presentation_id": self.presentation_id,
            "processing": {
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "duration_seconds": self.duration_seconds,
                "status": self.status.value,
            },
            "audio": {
                "duration_seconds": self.audio_duration_seconds,
                "format": self.audio_format,
                "sample_rate": self.audio_sample_rate,
                "channels": self.audio_channels,
                "size_bytes": self.audio_size_bytes,
            },
            "google_cloud": {
                "operation_id": self.operation_id,
                "model": self.model,
                "language": self.language,
                "features": self.features,
            },
            "quality": {
                "overall_confidence": self.overall_confidence,
                "low_confidence_segments": self.low_confidence_segments,
                "flags": self.quality_flags,
            },
            "cost": {
                "processing_minutes": self.processing_minutes,
                "estimated_cost_usd": self.estimated_cost_usd,
            },
        }

