"""
Speech-to-Text Package - Google Cloud Migration
"""
# Core modules
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
    'Database',
    'Presentation',
    'AudioFile',
    'SlideFile',
    'Transcript',
    'TranscriptSegment',
    'PresentationStatus'
]

__version__ = '2.0.0-phase1'
