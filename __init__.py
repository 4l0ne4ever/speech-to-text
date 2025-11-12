"""
Speech-to-Text Package using AssemblyAI with S3 Integration
"""
from .speech_to_text import SpeechToText
from .s3_storage import S3Storage
from .processor import SpeechToTextProcessor
from .presentation_manager import PresentationManager
from .database import Database
from .models import (
    Presentation,
    AudioFile,
    SlideFile,
    Transcript,
    TranscriptSegment,
    PresentationStatus
)

__all__ = [
    'SpeechToText',
    'S3Storage',
    'SpeechToTextProcessor',
    'PresentationManager',
    'Database',
    'Presentation',
    'AudioFile',
    'SlideFile',
    'Transcript',
    'TranscriptSegment',
    'PresentationStatus'
]
__version__ = '1.0.0'
