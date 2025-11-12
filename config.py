"""
Configuration file for AssemblyAI Speech-to-Text
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# AssemblyAI API Key
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

if not ASSEMBLYAI_API_KEY:
    raise ValueError("ASSEMBLYAI_API_KEY not found in environment variables. Please add it to your .env file.")

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")  # Default: Japan
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# Local storage for downloaded files
DOWNLOAD_FOLDER = os.getenv("DOWNLOAD_FOLDER", "./downloads")

# Default language for transcription
# Supported languages: ja (Japanese), en (English), vi (Vietnamese), zh (Chinese), ko (Korean), etc.
DEFAULT_LANGUAGE = "ja"  # Tiếng Nhật

# Other transcription settings
DEFAULT_CONFIG = {
    "language_code": DEFAULT_LANGUAGE,
    "punctuate": True,        # Tự động thêm dấu câu
    "format_text": True,      # Format text
}

# S3 Folder Structure
S3_PRESENTATIONS_PREFIX = "presentations"
S3_TEMP_PREFIX = "temp"
