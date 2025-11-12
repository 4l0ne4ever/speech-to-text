"""
Presentation Manager - Quản lý presentations với audio + PDF slides
Tích hợp S3 + Database + Speech-to-Text
"""
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

from s3_storage import S3Storage
from speech_to_text import SpeechToText
from database import Database
from models import PresentationStatus
from config import S3_PRESENTATIONS_PREFIX


class PresentationManager:
    """
    Manager để xử lý presentations (audio + slides)
    
    Workflow:
    1. Upload audio + slide lên S3
    2. Tạo records trong database
    3. Transcribe audio (optional)
    4. Lưu transcript vào database
    """
    
    def __init__(self, db_file: str = "database.json"):
        """
        Initialize PresentationManager
        
        Args:
            db_file: Path to database file
        """
        self.s3 = S3Storage()
        self.stt = SpeechToText()
        self.db = Database(db_file)
    
    def _generate_presentation_id(self) -> str:
        """Generate unique presentation ID"""
        date_str = datetime.now().strftime("%Y%m%d")
        unique_id = str(uuid.uuid4())[:8]
        return f"pres_{date_str}_{unique_id}"
    
    def create_presentation(
        self,
        audio_file_path: str,
        slide_file_path: Optional[str] = None,
        title: str = "",
        description: Optional[str] = None,
        language: str = "ja",
        auto_transcribe: bool = False
    ) -> Dict:
        """
        Tạo presentation mới với audio + PDF slides (optional)
        
        Args:
            audio_file_path: Đường dẫn file audio local
            slide_file_path: Đường dẫn file PDF local (optional)
            title: Tiêu đề presentation
            description: Mô tả
            language: Ngôn ngữ audio
            auto_transcribe: Tự động transcribe sau khi upload
            
        Returns:
            dict: Kết quả với presentation info
        """
        try:
            # Validate audio file exists
            if not os.path.exists(audio_file_path):
                return {"success": False, "error": f"Audio file not found: {audio_file_path}"}
            
            # Validate slide file if provided
            if slide_file_path and not os.path.exists(slide_file_path):
                return {"success": False, "error": f"Slide file not found: {slide_file_path}"}
            
            # Generate presentation ID
            presentation_id = self._generate_presentation_id()
            
            print(f"📊 Creating presentation: {presentation_id}")
            print(f"   Title: {title}")
            
            # Get audio file info
            audio_name = os.path.basename(audio_file_path)
            audio_ext = Path(audio_file_path).suffix
            audio_size = os.path.getsize(audio_file_path)
            
            # Define S3 keys
            audio_s3_key = f"{S3_PRESENTATIONS_PREFIX}/{presentation_id}/audio/original{audio_ext}"
            
            # Upload audio to S3
            print(f"📤 Uploading audio: {audio_name}")
            audio_upload = self.s3.upload_file(audio_file_path, audio_s3_key)
            if not audio_upload["success"]:
                return {"success": False, "error": f"Failed to upload audio: {audio_upload['error']}"}
            
            # Upload slide to S3 if provided
            slide_s3_key = None
            if slide_file_path:
                slide_name = os.path.basename(slide_file_path)
                slide_size = os.path.getsize(slide_file_path)
                slide_s3_key = f"{S3_PRESENTATIONS_PREFIX}/{presentation_id}/slides/original.pdf"
                
                print(f"📤 Uploading slide: {slide_name}")
                slide_upload = self.s3.upload_file(slide_file_path, slide_s3_key)
                if not slide_upload["success"]:
                    # Rollback: delete uploaded audio
                    self.s3.delete_file(audio_s3_key)
                    return {"success": False, "error": f"Failed to upload slide: {slide_upload['error']}"}
            
            # Create presentation record in database
            print(f"💾 Saving to database...")
            presentation = self.db.create_presentation(
                presentation_id=presentation_id,
                title=title,
                description=description,
                language=language
            )
            
            presentation_pk = presentation["id"]
            
            # Create audio file record
            audio_file = self.db.create_audio_file(
                presentation_id=presentation_pk,
                s3_key=audio_s3_key,
                file_name=audio_name,
                file_size=audio_size,
                format=audio_ext.lstrip('.')
            )
            
            # Create slide file record if slide was uploaded
            slide_file = None
            if slide_file_path:
                slide_file = self.db.create_slide_file(
                    presentation_id=presentation_pk,
                    s3_key=slide_s3_key,
                    file_name=slide_name,
                    file_size=slide_size
                )
            
            print(f"✅ Presentation created successfully!")
            
            result = {
                "success": True,
                "presentation_id": presentation_id,
                "presentation": presentation,
                "audio_file": audio_file,
                "slide_file": slide_file,
                "audio_s3_key": audio_s3_key,
                "slide_s3_key": slide_s3_key
            }
            
            # Auto transcribe if requested
            if auto_transcribe:
                print(f"\n🎤 Starting auto-transcription...")
                transcribe_result = self.transcribe_presentation(presentation_id)
                result["transcription"] = transcribe_result
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to create presentation: {str(e)}"
            }
    
    def transcribe_presentation(
        self,
        presentation_id: str,
        speaker_labels: bool = False
    ) -> Dict:
        """
        Transcribe audio của presentation
        
        Args:
            presentation_id: ID của presentation
            speaker_labels: Có nhận diện speakers không
            
        Returns:
            dict: Kết quả transcription
        """
        try:
            # Get presentation từ database
            presentation = self.db.get_presentation_by_id(presentation_id)
            if not presentation:
                return {"success": False, "error": "Presentation not found"}
            
            presentation_pk = presentation["id"]
            language = presentation["language"]
            
            # Get audio file
            audio_file = self.db.get_audio_file_by_presentation(presentation_pk)
            if not audio_file:
                return {"success": False, "error": "Audio file not found"}
            
            # Update status to processing
            self.db.update_presentation(presentation_id, status=PresentationStatus.PROCESSING.value)
            
            print(f"🎤 Transcribing presentation: {presentation_id}")
            
            # Generate presigned URL for audio
            audio_s3_key = audio_file["s3_key"]
            url_result = self.s3.generate_presigned_url(audio_s3_key, expiration=7200)
            
            if not url_result["success"]:
                self.db.update_presentation(presentation_id, status=PresentationStatus.FAILED.value)
                return {"success": False, "error": f"Failed to generate URL: {url_result['error']}"}
            
            audio_url = url_result["presigned_url"]
            
            # Transcribe using AssemblyAI
            if speaker_labels:
                transcript_result = self.stt.transcribe_with_config(
                    audio_url,
                    language_code=language,
                    speaker_labels=True
                )
            else:
                transcript_result = self.stt.transcribe_url(audio_url, language)
            
            if not transcript_result["success"]:
                self.db.update_presentation(presentation_id, status=PresentationStatus.FAILED.value)
                return {"success": False, "error": f"Transcription failed: {transcript_result['error']}"}
            
            # Save transcript to database
            transcript_text = transcript_result["text"]
            word_count = len(transcript_text.split()) if transcript_text else 0
            
            transcript = self.db.create_transcript(
                audio_file_id=audio_file["id"],
                presentation_id=presentation_pk,
                text=transcript_text,
                language_detected=transcript_result.get("language", language),
                confidence=transcript_result.get("confidence", 0.0),
                word_count=word_count
            )
            
            # Save segments if speaker labels enabled
            if speaker_labels and "speakers" in transcript_result:
                for i, speaker_data in enumerate(transcript_result["speakers"]):
                    self.db.create_segment(
                        transcript_id=transcript["id"],
                        text=speaker_data["text"],
                        start_time=speaker_data["start"] / 1000.0,  # Convert ms to seconds
                        end_time=speaker_data["end"] / 1000.0,
                        confidence=transcript_result.get("confidence", 0.0),
                        speaker_label=speaker_data["speaker"],
                        segment_order=i
                    )
            
            # Update presentation status to completed
            duration = transcript_result.get("audio_duration", 0) / 1000.0  # ms to seconds
            self.db.update_presentation(
                presentation_id,
                status=PresentationStatus.COMPLETED.value,
                duration=duration
            )
            
            print(f"✅ Transcription completed!")
            print(f"   Words: {word_count}")
            print(f"   Confidence: {transcript_result.get('confidence', 0.0)}")
            
            return {
                "success": True,
                "presentation_id": presentation_id,
                "transcript": transcript,
                "text": transcript_text,
                "word_count": word_count,
                "confidence": transcript_result.get("confidence", 0.0)
            }
            
        except Exception as e:
            self.db.update_presentation(presentation_id, status=PresentationStatus.FAILED.value)
            return {
                "success": False,
                "error": f"Transcription error: {str(e)}"
            }
    
    def get_presentation(self, presentation_id: str) -> Optional[Dict]:
        """
        Lấy presentation với tất cả thông tin liên quan
        
        Args:
            presentation_id: ID của presentation
            
        Returns:
            dict: Full presentation data
        """
        return self.db.get_presentation_with_files(presentation_id)
    
    def list_presentations(
        self,
        status: Optional[str] = None,
        language: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        List presentations với filters
        
        Args:
            status: Filter by status
            language: Filter by language
            limit: Max results
            
        Returns:
            list: Danh sách presentations
        """
        return self.db.list_presentations(status, language, limit)
    
    def delete_presentation(self, presentation_id: str, delete_files: bool = True) -> Dict:
        """
        Xóa presentation và files
        
        Args:
            presentation_id: ID của presentation
            delete_files: Có xóa files trên S3 không
            
        Returns:
            dict: Kết quả xóa
        """
        try:
            if delete_files:
                # Get file info before deleting from DB
                presentation_data = self.db.get_presentation_with_files(presentation_id)
                
                if presentation_data:
                    # Delete audio from S3
                    if presentation_data["audio_file"]:
                        self.s3.delete_file(presentation_data["audio_file"]["s3_key"])
                    
                    # Delete slide from S3
                    if presentation_data["slide_file"]:
                        self.s3.delete_file(presentation_data["slide_file"]["s3_key"])
                    
                    print(f"🗑️  Deleted files from S3")
            
            # Delete from database
            deleted = self.db.delete_presentation(presentation_id)
            
            if not deleted:
                return {"success": False, "error": "Presentation not found"}
            
            print(f"✅ Presentation deleted: {presentation_id}")
            
            return {
                "success": True,
                "presentation_id": presentation_id,
                "message": "Presentation deleted successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Delete failed: {str(e)}"
            }
    
    def get_audio_url(self, presentation_id: str, expiration: int = 3600) -> Dict:
        """Generate presigned URL cho audio"""
        presentation = self.db.get_presentation_by_id(presentation_id)
        if not presentation:
            return {"success": False, "error": "Presentation not found"}
        
        audio_file = self.db.get_audio_file_by_presentation(presentation["id"])
        if not audio_file:
            return {"success": False, "error": "Audio file not found"}
        
        return self.s3.generate_presigned_url(audio_file["s3_key"], expiration)
    
    def get_slide_url(self, presentation_id: str, expiration: int = 3600) -> Dict:
        """Generate presigned URL cho slide PDF"""
        presentation = self.db.get_presentation_by_id(presentation_id)
        if not presentation:
            return {"success": False, "error": "Presentation not found"}
        
        slide_file = self.db.get_slide_file_by_presentation(presentation["id"])
        if not slide_file:
            return {"success": False, "error": "Slide file not found"}
        
        return self.s3.generate_presigned_url(slide_file["s3_key"], expiration)
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        return self.db.get_statistics()
