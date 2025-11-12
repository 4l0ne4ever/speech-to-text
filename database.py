"""
Database Module - JSON-based storage (Simple implementation)
For production, replace with PostgreSQL/MySQL
"""
import json
import os
from typing import Optional, List, Dict
from datetime import datetime
from models import (
    Presentation, AudioFile, SlideFile, Transcript, TranscriptSegment,
    PresentationStatus
)


class Database:
    """
    Simple JSON-based database
    
    Structure:
    {
        "presentations": [],
        "audio_files": [],
        "slide_files": [],
        "transcripts": [],
        "transcript_segments": []
    }
    """
    
    def __init__(self, db_file: str = "database.json"):
        """
        Initialize database
        
        Args:
            db_file: Path to JSON file
        """
        self.db_file = db_file
        self._init_db()
    
    def _init_db(self):
        """Initialize database file if not exists"""
        if not os.path.exists(self.db_file):
            initial_data = {
                "presentations": [],
                "audio_files": [],
                "slide_files": [],
                "transcripts": [],
                "transcript_segments": [],
                "_counters": {
                    "presentation": 0,
                    "audio_file": 0,
                    "slide_file": 0,
                    "transcript": 0,
                    "segment": 0
                }
            }
            self._write(initial_data)
    
    def _read(self) -> Dict:
        """Read database"""
        with open(self.db_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _write(self, data: Dict):
        """Write database"""
        with open(self.db_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def _get_next_id(self, table: str) -> int:
        """Get next auto-increment ID"""
        data = self._read()
        data["_counters"][table] += 1
        next_id = data["_counters"][table]
        self._write(data)
        return next_id
    
    # ==================== PRESENTATIONS ====================
    
    def create_presentation(
        self,
        presentation_id: str,
        title: str,
        description: Optional[str] = None,
        language: str = "ja",
        user_id: Optional[int] = None
    ) -> Presentation:
        """Create new presentation"""
        data = self._read()
        
        presentation = {
            "id": self._get_next_id("presentation"),
            "presentation_id": presentation_id,
            "title": title,
            "description": description,
            "language": language,
            "duration": None,
            "status": PresentationStatus.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "user_id": user_id
        }
        
        data["presentations"].append(presentation)
        self._write(data)
        
        return presentation
    
    def get_presentation_by_id(self, presentation_id: str) -> Optional[Dict]:
        """Get presentation by business ID"""
        data = self._read()
        for p in data["presentations"]:
            if p["presentation_id"] == presentation_id:
                return p
        return None
    
    def get_presentation_by_pk(self, pk: int) -> Optional[Dict]:
        """Get presentation by primary key"""
        data = self._read()
        for p in data["presentations"]:
            if p["id"] == pk:
                return p
        return None
    
    def update_presentation(self, presentation_id: str, **kwargs) -> Optional[Dict]:
        """Update presentation"""
        data = self._read()
        
        for i, p in enumerate(data["presentations"]):
            if p["presentation_id"] == presentation_id:
                for key, value in kwargs.items():
                    if key in p:
                        p[key] = value
                p["updated_at"] = datetime.now().isoformat()
                data["presentations"][i] = p
                self._write(data)
                return p
        
        return None
    
    def list_presentations(
        self,
        status: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """List presentations with filters"""
        data = self._read()
        presentations = data["presentations"]
        
        # Apply filters
        if status:
            presentations = [p for p in presentations if p["status"] == status]
        if language:
            presentations = [p for p in presentations if p["language"] == language]
        
        # Sort by created_at descending
        presentations.sort(key=lambda x: x["created_at"], reverse=True)
        
        return presentations[offset:offset + limit]
    
    def delete_presentation(self, presentation_id: str) -> bool:
        """Delete presentation and related records"""
        data = self._read()
        
        # Find presentation
        presentation = None
        for i, p in enumerate(data["presentations"]):
            if p["presentation_id"] == presentation_id:
                presentation = data["presentations"].pop(i)
                break
        
        if not presentation:
            return False
        
        presentation_pk = presentation["id"]
        
        # Delete related audio files
        data["audio_files"] = [
            af for af in data["audio_files"]
            if af["presentation_id"] != presentation_pk
        ]
        
        # Delete related slide files
        data["slide_files"] = [
            sf for sf in data["slide_files"]
            if sf["presentation_id"] != presentation_pk
        ]
        
        # Delete related transcripts
        data["transcripts"] = [
            t for t in data["transcripts"]
            if t["presentation_id"] != presentation_pk
        ]
        
        # Delete related segments
        # (need to find transcript IDs first, but for simplicity we skip)
        
        self._write(data)
        return True
    
    # ==================== AUDIO FILES ====================
    
    def create_audio_file(
        self,
        presentation_id: int,
        s3_key: str,
        file_name: str,
        file_size: int,
        format: str = "mp3"
    ) -> Dict:
        """Create audio file record"""
        data = self._read()
        
        audio_file = {
            "id": self._get_next_id("audio_file"),
            "presentation_id": presentation_id,
            "s3_key": s3_key,
            "s3_url": None,
            "file_name": file_name,
            "file_size": file_size,
            "format": format,
            "duration": None,
            "upload_status": "uploaded",
            "uploaded_at": datetime.now().isoformat(),
            "checksum": None
        }
        
        data["audio_files"].append(audio_file)
        self._write(data)
        
        return audio_file
    
    def get_audio_file_by_presentation(self, presentation_id: int) -> Optional[Dict]:
        """Get audio file by presentation ID"""
        data = self._read()
        for af in data["audio_files"]:
            if af["presentation_id"] == presentation_id:
                return af
        return None
    
    # ==================== SLIDE FILES ====================
    
    def create_slide_file(
        self,
        presentation_id: int,
        s3_key: str,
        file_name: str,
        file_size: int
    ) -> Dict:
        """Create slide file record"""
        data = self._read()
        
        slide_file = {
            "id": self._get_next_id("slide_file"),
            "presentation_id": presentation_id,
            "s3_key": s3_key,
            "s3_url": None,
            "file_name": file_name,
            "file_size": file_size,
            "page_count": None,
            "upload_status": "uploaded",
            "uploaded_at": datetime.now().isoformat(),
            "checksum": None
        }
        
        data["slide_files"].append(slide_file)
        self._write(data)
        
        return slide_file
    
    def get_slide_file_by_presentation(self, presentation_id: int) -> Optional[Dict]:
        """Get slide file by presentation ID"""
        data = self._read()
        for sf in data["slide_files"]:
            if sf["presentation_id"] == presentation_id:
                return sf
        return None
    
    # ==================== TRANSCRIPTS ====================
    
    def create_transcript(
        self,
        audio_file_id: int,
        presentation_id: int,
        text: str,
        language_detected: str,
        confidence: float,
        word_count: int
    ) -> Dict:
        """Create transcript record"""
        data = self._read()
        
        transcript = {
            "id": self._get_next_id("transcript"),
            "audio_file_id": audio_file_id,
            "presentation_id": presentation_id,
            "text": text,
            "language_detected": language_detected,
            "confidence": confidence,
            "processing_status": "completed",
            "processed_at": datetime.now().isoformat(),
            "word_count": word_count
        }
        
        data["transcripts"].append(transcript)
        self._write(data)
        
        return transcript
    
    def get_transcript_by_presentation(self, presentation_id: int) -> Optional[Dict]:
        """Get transcript by presentation ID"""
        data = self._read()
        for t in data["transcripts"]:
            if t["presentation_id"] == presentation_id:
                return t
        return None
    
    # ==================== TRANSCRIPT SEGMENTS ====================
    
    def create_segment(
        self,
        transcript_id: int,
        text: str,
        start_time: float,
        end_time: float,
        confidence: float,
        speaker_label: Optional[str],
        segment_order: int
    ) -> Dict:
        """Create transcript segment"""
        data = self._read()
        
        segment = {
            "id": self._get_next_id("segment"),
            "transcript_id": transcript_id,
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
            "confidence": confidence,
            "speaker_label": speaker_label,
            "segment_order": segment_order
        }
        
        data["transcript_segments"].append(segment)
        self._write(data)
        
        return segment
    
    def get_segments_by_transcript(self, transcript_id: int) -> List[Dict]:
        """Get all segments for a transcript"""
        data = self._read()
        segments = [
            s for s in data["transcript_segments"]
            if s["transcript_id"] == transcript_id
        ]
        segments.sort(key=lambda x: x["segment_order"])
        return segments
    
    # ==================== UTILITIES ====================
    
    def get_presentation_with_files(self, presentation_id: str) -> Optional[Dict]:
        """Get presentation với audio, slide, và transcript"""
        presentation = self.get_presentation_by_id(presentation_id)
        if not presentation:
            return None
        
        presentation_pk = presentation["id"]
        
        result = {
            "presentation": presentation,
            "audio_file": self.get_audio_file_by_presentation(presentation_pk),
            "slide_file": self.get_slide_file_by_presentation(presentation_pk),
            "transcript": self.get_transcript_by_presentation(presentation_pk)
        }
        
        return result
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        data = self._read()
        
        stats = {
            "total_presentations": len(data["presentations"]),
            "total_audio_files": len(data["audio_files"]),
            "total_slide_files": len(data["slide_files"]),
            "total_transcripts": len(data["transcripts"]),
            "by_status": {},
            "by_language": {}
        }
        
        for p in data["presentations"]:
            status = p["status"]
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            lang = p["language"]
            stats["by_language"][lang] = stats["by_language"].get(lang, 0) + 1
        
        return stats
