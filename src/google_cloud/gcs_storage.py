"""
Google Cloud Storage wrapper for intermediate file storage
Phase 1 - Week 2: AWS Integration and File Transfer Pipeline
"""
import os
from typing import Optional, Dict
from google.cloud import storage
from google.api_core import exceptions
import logging

logger = logging.getLogger(__name__)


class GCSStorage:
    """
    Google Cloud Storage client for managing intermediate audio files
    
    This class provides methods to:
    - Upload files from local filesystem to GCS
    - Download files from GCS to local filesystem  
    - Generate signed URLs for API access
    - List and delete files
    - Handle cleanup of temporary files
    
    Per plan: "Create a Google Cloud Storage bucket for intermediate file storage.
    Set up lifecycle rules to automatically delete files older than seven days."
    """
    
    def __init__(
        self,
        bucket_name: str,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize GCS client
        
        Args:
            bucket_name: GCS bucket name (e.g., "speech-processing-intermediate")
            credentials_path: Path to service account JSON key file
        """
        # Set credentials if provided
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        
        try:
            self.client = storage.Client()
            self.bucket_name = bucket_name
            self.bucket = self.client.bucket(bucket_name)
            
            # Verify bucket exists
            if not self.bucket.exists():
                raise ValueError(
                    f"Bucket '{bucket_name}' does not exist. "
                    f"Please create it first using: "
                    f"gsutil mb -l <region> gs://{bucket_name}"
                )
            
            logger.info(f"✅ GCS client initialized for bucket: {bucket_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize GCS client: {e}")
            raise
    
    def upload_file(
        self,
        local_file_path: str,
        gcs_key: str,
        content_type: Optional[str] = None
    ) -> Dict:
        """
        Upload a file from local filesystem to GCS
        
        Args:
            local_file_path: Path to local file
            gcs_key: Destination key in GCS (e.g., "temp/pres_123/audio.mp3")
            content_type: MIME type (auto-detected if None)
            
        Returns:
            dict: {
                "success": True/False,
                "gcs_uri": "gs://bucket/key",
                "gcs_key": "key",
                "size": bytes,
                "error": "error message" (if failed)
            }
        """
        try:
            # Validate local file exists
            if not os.path.exists(local_file_path):
                return {
                    "success": False,
                    "error": f"Local file not found: {local_file_path}"
                }
            
            # Get file size
            file_size = os.path.getsize(local_file_path)
            
            # Create blob
            blob = self.bucket.blob(gcs_key)
            
            # Set content type if provided
            if content_type:
                blob.content_type = content_type
            
            # Upload file
            logger.info(f"📤 Uploading {local_file_path} to gs://{self.bucket_name}/{gcs_key}")
            blob.upload_from_filename(local_file_path)
            
            gcs_uri = f"gs://{self.bucket_name}/{gcs_key}"
            
            logger.info(f"✅ Upload successful: {gcs_uri} ({file_size} bytes)")
            
            return {
                "success": True,
                "gcs_uri": gcs_uri,
                "gcs_key": gcs_key,
                "size": file_size
            }
            
        except exceptions.GoogleAPIError as e:
            logger.error(f"❌ GCS API error during upload: {e}")
            return {
                "success": False,
                "error": f"GCS API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def download_file(
        self,
        gcs_key: str,
        local_file_path: str
    ) -> Dict:
        """
        Download a file from GCS to local filesystem
        
        Args:
            gcs_key: Source key in GCS
            local_file_path: Destination path on local filesystem
            
        Returns:
            dict: {
                "success": True/False,
                "local_path": "path",
                "size": bytes,
                "error": "error message" (if failed)
            }
        """
        try:
            # Create blob reference
            blob = self.bucket.blob(gcs_key)
            
            # Check if blob exists
            if not blob.exists():
                return {
                    "success": False,
                    "error": f"File not found in GCS: gs://{self.bucket_name}/{gcs_key}"
                }
            
            # Create directory if needed
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            # Download file
            logger.info(f"📥 Downloading gs://{self.bucket_name}/{gcs_key} to {local_file_path}")
            blob.download_to_filename(local_file_path)
            
            file_size = os.path.getsize(local_file_path)
            
            logger.info(f"✅ Download successful: {local_file_path} ({file_size} bytes)")
            
            return {
                "success": True,
                "local_path": local_file_path,
                "size": file_size
            }
            
        except exceptions.GoogleAPIError as e:
            logger.error(f"❌ GCS API error during download: {e}")
            return {
                "success": False,
                "error": f"GCS API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_file(self, gcs_key: str) -> Dict:
        """
        Delete a file from GCS
        
        Args:
            gcs_key: Key to delete
            
        Returns:
            dict: {"success": True/False, "error": "message"}
        """
        try:
            blob = self.bucket.blob(gcs_key)
            
            if not blob.exists():
                logger.warning(f"⚠️  File not found (already deleted?): gs://{self.bucket_name}/{gcs_key}")
                return {"success": True}  # Consider already deleted as success
            
            blob.delete()
            
            logger.info(f"🗑️  Deleted: gs://{self.bucket_name}/{gcs_key}")
            
            return {"success": True}
            
        except exceptions.GoogleAPIError as e:
            logger.error(f"❌ GCS API error during delete: {e}")
            return {
                "success": False,
                "error": f"GCS API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Delete failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def file_exists(self, gcs_key: str) -> bool:
        """Check if a file exists in GCS"""
        try:
            blob = self.bucket.blob(gcs_key)
            return blob.exists()
        except Exception as e:
            logger.error(f"❌ Error checking file existence: {e}")
            return False
    
    def list_files(self, prefix: str = "") -> Dict:
        """
        List files in GCS bucket with given prefix
        
        Args:
            prefix: Key prefix to filter (e.g., "temp/")
            
        Returns:
            dict: {
                "success": True/False,
                "files": [{"key": "...", "size": bytes, "updated": datetime}, ...],
                "count": int,
                "error": "message"
            }
        """
        try:
            blobs = self.bucket.list_blobs(prefix=prefix)
            
            files = []
            for blob in blobs:
                files.append({
                    "key": blob.name,
                    "size": blob.size,
                    "updated": blob.updated,
                    "content_type": blob.content_type
                })
            
            logger.info(f"📋 Listed {len(files)} files with prefix '{prefix}'")
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
            
        except exceptions.GoogleAPIError as e:
            logger.error(f"❌ GCS API error during list: {e}")
            return {
                "success": False,
                "files": [],
                "count": 0,
                "error": f"GCS API error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ List failed: {e}")
            return {
                "success": False,
                "files": [],
                "count": 0,
                "error": str(e)
            }
    
    def cleanup_presentation(self, presentation_id: str) -> Dict:
        """
        Delete all files for a presentation
        
        Args:
            presentation_id: Presentation ID (e.g., "pres_20251113_abc123")
            
        Returns:
            dict: {
                "success": True/False,
                "deleted_count": int,
                "error": "message"
            }
        """
        try:
            prefix = f"temp/{presentation_id}/"
            
            # List all files
            result = self.list_files(prefix)
            if not result["success"]:
                return result
            
            files = result["files"]
            deleted_count = 0
            
            # Delete each file
            for file_info in files:
                delete_result = self.delete_file(file_info["key"])
                if delete_result["success"]:
                    deleted_count += 1
            
            logger.info(f"🗑️  Cleaned up {deleted_count} files for presentation {presentation_id}")
            
            return {
                "success": True,
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}")
            return {
                "success": False,
                "deleted_count": 0,
                "error": str(e)
            }
    
    def get_signed_url(
        self,
        gcs_key: str,
        expiration: int = 3600
    ) -> Dict:
        """
        Generate a signed URL for temporary access
        
        Args:
            gcs_key: File key in GCS
            expiration: URL expiration in seconds (default: 1 hour)
            
        Returns:
            dict: {
                "success": True/False,
                "signed_url": "https://...",
                "expires_in": seconds,
                "error": "message"
            }
        """
        try:
            blob = self.bucket.blob(gcs_key)
            
            if not blob.exists():
                return {
                    "success": False,
                    "error": f"File not found: gs://{self.bucket_name}/{gcs_key}"
                }
            
            # Generate signed URL
            url = blob.generate_signed_url(
                version="v4",
                expiration=expiration,
                method="GET"
            )
            
            logger.info(f"🔗 Generated signed URL for {gcs_key} (expires in {expiration}s)")
            
            return {
                "success": True,
                "signed_url": url,
                "expires_in": expiration
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate signed URL: {e}")
            return {
                "success": False,
                "error": str(e)
            }
