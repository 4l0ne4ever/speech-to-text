"""
Result storage service for saving transcription results to Google Cloud Storage.

This module handles storing processed transcription results in GCS with proper
structure and atomic write operations. Results are stored as JSON files with
separate files for transcript, word-level details, and metadata.
"""

import json
import logging
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from google.cloud import storage
from google.api_core import exceptions as google_exceptions

from ..models import TranscriptionResult, ProcessingMetadata

logger = logging.getLogger(__name__)


class ResultStorageError(Exception):
    """Base exception for result storage errors."""
    pass


class GCSResultStorage:
    """
    Service for storing transcription results in Google Cloud Storage.
    
    This service handles:
    - JSON serialization of results
    - Atomic write operations
    - Retry logic for reliability
    - Proper GCS path structure
    """
    
    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize GCS result storage.
        
        Args:
            bucket_name: Name of GCS bucket for results
            credentials_path: Path to service account JSON key
        """
        if credentials_path:
            self.client = storage.Client.from_service_account_json(credentials_path)
        else:
            self.client = storage.Client()
        
        self.bucket_name = bucket_name
        self.bucket = self.client.bucket(bucket_name)
        
        logger.info(f"GCSResultStorage initialized for bucket: {bucket_name}")
    
    def save_transcription_result(
        self,
        result: TranscriptionResult,
        presentation_id: str
    ) -> Dict[str, str]:
        """
        Save complete transcription result to GCS.
        
        Creates three files:
        - transcript.json: Full transcript with segments
        - words.json: Word-level details (can be large)
        - metadata.json: Processing metadata
        
        Args:
            result: TranscriptionResult object
            presentation_id: Presentation ID for path structure
            
        Returns:
            Dictionary with GCS URIs of saved files
            
        Raises:
            ResultStorageError: If save operation fails
        """
        logger.info(f"Saving transcription result for {presentation_id}")
        
        try:
            # Prepare paths
            base_path = f"presentations/{presentation_id}/transcripts"
            
            # Save transcript.json
            transcript_uri = self._save_transcript_json(result, base_path)
            
            # Save words.json (if words exist)
            words_uri = None
            if result.words:
                words_uri = self._save_words_json(result, base_path)
            
            # Save metadata.json
            metadata_uri = self._save_metadata_json(result, base_path)
            
            uris = {
                "transcript": transcript_uri,
                "words": words_uri,
                "metadata": metadata_uri,
            }
            
            logger.info(
                f"Successfully saved transcription result for {presentation_id}: "
                f"transcript={transcript_uri}, words={words_uri}, metadata={metadata_uri}"
            )
            
            return uris
            
        except Exception as e:
            logger.error(f"Failed to save transcription result: {e}", exc_info=True)
            raise ResultStorageError(f"Failed to save transcription result: {e}")
    
    def _save_transcript_json(
        self,
        result: TranscriptionResult,
        base_path: str
    ) -> str:
        """Save transcript.json with full transcript and segments."""
        data = {
            "presentation_id": result.presentation_id,
            "language": result.language,
            "model": result.model,
            "transcript": {
                "full_text": result.transcript,
                "confidence": result.confidence,
                "duration_seconds": result.duration_seconds,
                "word_count": result.word_count,
            },
            "segments": [
                {
                    "segment_id": seg.segment_id,
                    "text": seg.text,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "confidence": seg.confidence,
                    "word_count": seg.word_count,
                }
                for seg in result.segments
            ],
            "processing": {
                "processed_at": datetime.utcnow().isoformat() + "Z",
                "processing_duration_seconds": result.processing_time_seconds,
                "gcs_uri": result.gcs_uri,
                "operation_id": result.operation_id,
            },
            "quality": {
                "has_low_confidence": result.has_low_confidence,
                "quality_flags": result.quality_flags,
            }
        }
        
        gcs_path = f"{base_path}/transcript.json"
        return self._write_json_to_gcs(data, gcs_path)
    
    def _save_words_json(
        self,
        result: TranscriptionResult,
        base_path: str
    ) -> str:
        """Save words.json with word-level details."""
        data = {
            "presentation_id": result.presentation_id,
            "words": [
                {
                    "word": word.word,
                    "start_time": word.start_time,
                    "end_time": word.end_time,
                    "confidence": word.confidence,
                }
                for word in result.words
            ],
            "total_words": len(result.words),
        }
        
        gcs_path = f"{base_path}/words.json"
        return self._write_json_to_gcs(data, gcs_path)
    
    def _save_metadata_json(
        self,
        result: TranscriptionResult,
        base_path: str
    ) -> str:
        """Save metadata.json with processing information."""
        # Calculate cost
        cost_per_15s = 0.024 if result.model == "chirp" else 0.009
        estimated_cost = (result.duration_seconds / 15) * cost_per_15s
        
        data = {
            "presentation_id": result.presentation_id,
            "processing": {
                "completed_at": datetime.utcnow().isoformat() + "Z",
                "duration_seconds": result.processing_time_seconds,
                "status": "completed",
            },
            "audio": {
                "duration_seconds": result.duration_seconds,
                "gcs_uri": result.gcs_uri,
            },
            "google_cloud": {
                "operation_id": result.operation_id,
                "model": result.model,
                "language": result.language,
            },
            "quality": {
                "overall_confidence": result.confidence,
                "has_low_confidence": result.has_low_confidence,
                "flags": result.quality_flags,
            },
            "cost": {
                "processing_minutes": result.duration_seconds / 60,
                "estimated_cost_usd": estimated_cost,
            },
        }
        
        gcs_path = f"{base_path}/metadata.json"
        return self._write_json_to_gcs(data, gcs_path)
    
    def _write_json_to_gcs(
        self,
        data: Dict[str, Any],
        gcs_path: str,
        max_retries: int = 3
    ) -> str:
        """
        Write JSON data to GCS with atomic operation and retry logic.
        
        Args:
            data: Dictionary to serialize as JSON
            gcs_path: Path in GCS bucket
            max_retries: Maximum retry attempts
            
        Returns:
            GCS URI of uploaded file
            
        Raises:
            ResultStorageError: If upload fails after retries
        """
        # Serialize to JSON
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        json_bytes = json_str.encode('utf-8')
        
        # Upload with retry
        for attempt in range(max_retries):
            try:
                blob = self.bucket.blob(gcs_path)
                
                # Upload with metadata
                blob.upload_from_string(
                    json_bytes,
                    content_type='application/json',
                    retry=storage.retry.DEFAULT_RETRY
                )
                
                gcs_uri = f"gs://{self.bucket_name}/{gcs_path}"
                
                logger.debug(f"Uploaded {gcs_path} ({len(json_bytes)} bytes)")
                
                return gcs_uri
                
            except google_exceptions.GoogleAPIError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Upload attempt {attempt + 1} failed for {gcs_path}, retrying: {e}"
                    )
                    continue
                else:
                    raise ResultStorageError(f"Failed to upload {gcs_path} after {max_retries} attempts: {e}")
            
            except Exception as e:
                logger.error(f"Unexpected error uploading {gcs_path}: {e}")
                raise ResultStorageError(f"Unexpected error uploading {gcs_path}: {e}")
    
    def get_transcription_result(
        self,
        presentation_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve transcription result from GCS.
        
        Args:
            presentation_id: Presentation ID
            
        Returns:
            Dictionary with transcript data, or None if not found
        """
        try:
            gcs_path = f"presentations/{presentation_id}/transcripts/transcript.json"
            blob = self.bucket.blob(gcs_path)
            
            if not blob.exists():
                logger.warning(f"Transcript not found: {gcs_path}")
                return None
            
            json_str = blob.download_as_text()
            data = json.loads(json_str)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to retrieve transcript: {e}")
            return None
    
    def delete_transcription_result(
        self,
        presentation_id: str
    ) -> int:
        """
        Delete all transcription files for a presentation.
        
        Args:
            presentation_id: Presentation ID
            
        Returns:
            Number of files deleted
        """
        try:
            prefix = f"presentations/{presentation_id}/transcripts/"
            blobs = list(self.bucket.list_blobs(prefix=prefix))
            
            deleted_count = 0
            for blob in blobs:
                blob.delete()
                deleted_count += 1
                logger.debug(f"Deleted {blob.name}")
            
            logger.info(f"Deleted {deleted_count} transcript files for {presentation_id}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete transcript files: {e}")
            raise ResultStorageError(f"Failed to delete transcript files: {e}")
