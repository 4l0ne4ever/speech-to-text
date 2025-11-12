"""
Speech-to-Text Processor with S3 Integration
Xử lý workflow: Upload → S3 Storage → Transcribe (qua presigned URL)
"""
from s3_storage import S3Storage
from speech_to_text import SpeechToText
import os


class SpeechToTextProcessor:
    """
    Class tích hợp S3 Storage và Speech-to-Text
    Workflow: Upload file → Lưu S3 → Transcribe trực tiếp từ S3 URL (không cần download)
    """
    
    def __init__(self):
        """Initialize S3Storage and SpeechToText"""
        self.s3_storage = S3Storage()
        self.stt = SpeechToText()
    
    def upload_audio(self, local_file_path: str, s3_key: str = None) -> dict:
        """
        Bước 1: Upload audio file lên S3
        
        Args:
            local_file_path: Đường dẫn file audio local
            s3_key: Tên file trên S3 (optional)
            
        Returns:
            dict: Kết quả upload với s3_key và s3_url
        """
        print("=" * 60)
        print("BƯỚC 1: UPLOAD FILE LÊN S3")
        print("=" * 60)
        
        result = self.s3_storage.upload_file(local_file_path, s3_key)
        
        if result["success"]:
            print(f"✓ Upload thành công!")
            print(f"  S3 Key: {result['s3_key']}")
            print(f"  S3 URL: {result['s3_url']}")
        else:
            print(f"✗ Upload thất bại: {result['error']}")
        
        return result
    
    
    def process_audio_from_s3(self, s3_key: str, language_code: str = None, 
                              use_presigned_url: bool = True) -> dict:
        """
        Transcribe audio từ S3 (mặc định dùng presigned URL - không cần download)
        
        Args:
            s3_key: Tên file trên S3
            language_code: Mã ngôn ngữ (ja, en, vi, etc.)
            use_presigned_url: Dùng presigned URL (True) hoặc download file (False)
            
        Returns:
            dict: Kết quả transcription
        """
        if use_presigned_url:
            # Method 1: Dùng presigned URL (RECOMMENDED - nhanh hơn, không tốn disk)
            print("\n" + "=" * 60)
            print("BƯỚC 2: TẠO PRESIGNED URL TỪ S3")
            print("=" * 60)
            
            url_result = self.s3_storage.generate_presigned_url(s3_key, expiration=3600)
            
            if not url_result["success"]:
                print(f"✗ Tạo URL thất bại: {url_result['error']}")
                return url_result
            
            presigned_url = url_result["presigned_url"]
            print(f"✓ Đã tạo presigned URL (valid for {url_result['expires_in']}s)")
            
            # Transcribe trực tiếp từ URL
            print("\n" + "=" * 60)
            print("BƯỚC 3: TRANSCRIBE AUDIO TỪ S3 URL")
            print("=" * 60)
            
            transcribe_result = self.stt.transcribe_url(presigned_url, language_code)
            
        else:
            # Method 2: Download về rồi transcribe (fallback)
            print("\n" + "=" * 60)
            print("BƯỚC 2: DOWNLOAD FILE TỪ S3")
            print("=" * 60)
            
            download_result = self.s3_storage.download_file(s3_key)
            
            if not download_result["success"]:
                print(f"✗ Download thất bại: {download_result['error']}")
                return download_result
            
            local_file_path = download_result["local_path"]
            print(f"✓ Download thành công: {local_file_path}")
            
            # Transcribe file
            print("\n" + "=" * 60)
            print("BƯỚC 3: TRANSCRIBE AUDIO")
            print("=" * 60)
            
            transcribe_result = self.stt.transcribe_file(local_file_path, language_code)
            
            # Cleanup: Xóa file local sau khi transcribe
            if os.path.exists(local_file_path):
                try:
                    os.remove(local_file_path)
                    print(f"\n✓ Đã xóa file local: {local_file_path}")
                except Exception as e:
                    print(f"\n⚠ Không thể xóa file local: {str(e)}")
        
        # Thêm thông tin S3 vào kết quả
        if transcribe_result["success"]:
            transcribe_result["s3_key"] = s3_key
            transcribe_result["s3_bucket"] = self.s3_storage.bucket_name
            transcribe_result["method"] = "presigned_url" if use_presigned_url else "download"
        
        return transcribe_result
    
    
    def upload_and_transcribe(self, local_file_path: str, s3_key: str = None, 
                              language_code: str = None, use_presigned_url: bool = True) -> dict:
        """
        Full workflow: Upload → S3 → Transcribe (qua presigned URL)
        
        Args:
            local_file_path: Đường dẫn file audio local
            s3_key: Tên file trên S3 (optional)
            language_code: Mã ngôn ngữ (ja, en, vi, etc.)
            use_presigned_url: Dùng presigned URL (True) hoặc download file (False)
            
        Returns:
            dict: Kết quả transcription kèm thông tin S3
        """
        # Bước 1: Upload lên S3
        upload_result = self.upload_audio(local_file_path, s3_key)
        
        if not upload_result["success"]:
            return upload_result
        
        # Bước 2 & 3: Transcribe từ S3
        return self.process_audio_from_s3(
            upload_result["s3_key"],
            language_code=language_code,
            use_presigned_url=use_presigned_url
        )
    
    def transcribe_existing_s3_file(self, s3_key: str, language_code: str = None, 
                                    use_presigned_url: bool = True) -> dict:
        """
        Transcribe file đã có sẵn trên S3 (mặc định dùng presigned URL)
        
        Args:
            s3_key: Tên file trên S3
            language_code: Mã ngôn ngữ
            use_presigned_url: Dùng presigned URL (True) hoặc download file (False)
            
        Returns:
            dict: Kết quả transcription
        """
        # Kiểm tra file có tồn tại trên S3 không
        if not self.s3_storage.file_exists(s3_key):
            return {
                "success": False,
                "error": f"File không tồn tại trên S3: {s3_key}"
            }
        
        return self.process_audio_from_s3(s3_key, language_code, use_presigned_url)
    
    def list_audio_files(self, prefix: str = "") -> dict:
        """
        Liệt kê các file audio trên S3
        
        Args:
            prefix: Prefix để filter files
            
        Returns:
            dict: Danh sách files
        """
        return self.s3_storage.list_files(prefix)
    
    def delete_audio_from_s3(self, s3_key: str) -> dict:
        """
        Xóa file audio từ S3
        
        Args:
            s3_key: Tên file trên S3
            
        Returns:
            dict: Kết quả xóa file
        """
        return self.s3_storage.delete_file(s3_key)
