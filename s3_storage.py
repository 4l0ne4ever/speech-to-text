"""
S3 Storage Manager for handling file uploads and downloads
"""
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
    DOWNLOAD_FOLDER
)


class S3Storage:
    """
    Class để quản lý upload/download files từ AWS S3
    """
    
    def __init__(self):
        """Initialize S3 client"""
        if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
            raise ValueError("AWS credentials not found. Please add AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to .env file.")
        
        if not S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME not found. Please add it to .env file.")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.bucket_name = S3_BUCKET_NAME
        
        # Tạo folder downloads nếu chưa có
        if not os.path.exists(DOWNLOAD_FOLDER):
            os.makedirs(DOWNLOAD_FOLDER)
    
    def upload_file(self, local_file_path: str, s3_key: str = None) -> dict:
        """
        Upload file lên S3
        
        Args:
            local_file_path: Đường dẫn file local
            s3_key: Tên file trên S3 (nếu None sẽ dùng tên file gốc)
            
        Returns:
            dict: Kết quả upload với success status và s3_key
        """
        try:
            if not os.path.exists(local_file_path):
                return {
                    "success": False,
                    "error": f"File not found: {local_file_path}"
                }
            
            # Nếu không chỉ định s3_key, dùng tên file gốc
            if s3_key is None:
                s3_key = os.path.basename(local_file_path)
            
            print(f"Đang upload file '{local_file_path}' lên S3 bucket '{self.bucket_name}'...")
            
            self.s3_client.upload_file(local_file_path, self.bucket_name, s3_key)
            
            # Generate S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            
            return {
                "success": True,
                "s3_key": s3_key,
                "s3_url": s3_url,
                "bucket": self.bucket_name,
                "message": f"File uploaded successfully to {s3_key}"
            }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"File not found: {local_file_path}"
            }
        except NoCredentialsError:
            return {
                "success": False,
                "error": "AWS credentials not available"
            }
        except ClientError as e:
            return {
                "success": False,
                "error": f"AWS S3 error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Upload error: {str(e)}"
            }
    
    def download_file(self, s3_key: str, local_file_path: str = None) -> dict:
        """
        Download file từ S3 về local
        
        Args:
            s3_key: Tên file trên S3
            local_file_path: Đường dẫn lưu file local (nếu None sẽ lưu vào DOWNLOAD_FOLDER)
            
        Returns:
            dict: Kết quả download với success status và local_path
        """
        try:
            # Nếu không chỉ định local_file_path, lưu vào download folder
            if local_file_path is None:
                local_file_path = os.path.join(DOWNLOAD_FOLDER, os.path.basename(s3_key))
            
            # Tạo folder chứa file nếu chưa có
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
            
            print(f"Đang download file '{s3_key}' từ S3 bucket '{self.bucket_name}'...")
            
            self.s3_client.download_file(self.bucket_name, s3_key, local_file_path)
            
            return {
                "success": True,
                "local_path": local_file_path,
                "s3_key": s3_key,
                "message": f"File downloaded successfully to {local_file_path}"
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return {
                    "success": False,
                    "error": f"File not found in S3: {s3_key}"
                }
            return {
                "success": False,
                "error": f"AWS S3 error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Download error: {str(e)}"
            }
    
    def list_files(self, prefix: str = "") -> dict:
        """
        Liệt kê files trong S3 bucket
        
        Args:
            prefix: Prefix để filter files (ví dụ: "audio/")
            
        Returns:
            dict: Danh sách files trong bucket
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' not in response:
                return {
                    "success": True,
                    "files": [],
                    "count": 0
                }
            
            files = [
                {
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat()
                }
                for obj in response['Contents']
            ]
            
            return {
                "success": True,
                "files": files,
                "count": len(files)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"List files error: {str(e)}"
            }
    
    def delete_file(self, s3_key: str) -> dict:
        """
        Xóa file từ S3
        
        Args:
            s3_key: Tên file trên S3
            
        Returns:
            dict: Kết quả xóa file
        """
        try:
            print(f"Đang xóa file '{s3_key}' từ S3 bucket '{self.bucket_name}'...")
            
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            
            return {
                "success": True,
                "s3_key": s3_key,
                "message": f"File deleted successfully: {s3_key}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Delete error: {str(e)}"
            }
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Kiểm tra file có tồn tại trên S3 không
        
        Args:
            s3_key: Tên file trên S3
            
        Returns:
            bool: True nếu file tồn tại
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError:
            return False
    
    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> dict:
        """
        Tạo presigned URL để truy cập file trên S3 (không cần download)
        URL này có thể dùng trực tiếp với AssemblyAI
        
        Args:
            s3_key: Tên file trên S3
            expiration: Thời gian URL có hiệu lực (giây), mặc định 1 giờ
            
        Returns:
            dict: Kết quả với presigned URL
        """
        try:
            if not self.file_exists(s3_key):
                return {
                    "success": False,
                    "error": f"File không tồn tại trên S3: {s3_key}"
                }
            
            print(f"Đang tạo presigned URL cho file '{s3_key}'...")
            
            presigned_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            
            return {
                "success": True,
                "presigned_url": presigned_url,
                "s3_key": s3_key,
                "expires_in": expiration,
                "message": f"Presigned URL created (valid for {expiration} seconds)"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Generate presigned URL error: {str(e)}"
            }
