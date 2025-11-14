"""
Configuration for Google Cloud Platform services
Phase 1 - Week 1: Google Cloud Platform Setup
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# Google Cloud Configuration
# ============================================

# Service Account Credentials
# Per plan: "Download the service account JSON key file and store it securely.
# Never commit this key to version control, instead load it from environment variables."
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_SERVICE_ACCOUNT_KEY = os.getenv("GCP_SERVICE_ACCOUNT_KEY")  # Path to JSON key file

if not GCP_PROJECT_ID:
    raise ValueError(
        "GCP_PROJECT_ID not found. Please add it to .env file.\n"
        "Example: GCP_PROJECT_ID=speech-processing-prod"
    )

if not GCP_SERVICE_ACCOUNT_KEY:
    raise ValueError(
        "GCP_SERVICE_ACCOUNT_KEY not found. Please add path to service account JSON to .env file.\n"
        "Example: GCP_SERVICE_ACCOUNT_KEY=/path/to/service-account-key.json"
    )

# Verify service account key file exists
if not os.path.exists(GCP_SERVICE_ACCOUNT_KEY):
    raise FileNotFoundError(
        f"Service account key file not found: {GCP_SERVICE_ACCOUNT_KEY}\n"
        f"Please download it from Google Cloud Console and update .env"
    )

# Set as environment variable for Google Cloud libraries
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GCP_SERVICE_ACCOUNT_KEY

# ============================================
# Google Cloud Storage Configuration
# ============================================

# Per plan: "Create a Google Cloud Storage bucket for intermediate file storage.
# Choose a region close to your primary AWS S3 bucket to minimize transfer latency."
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "speech-processing-intermediate")
GCS_REGION = os.getenv("GCS_REGION", "asia-southeast1")  # Singapore region (close to AWS ap-southeast-1)

# Lifecycle: Auto-delete files older than 7 days
GCS_LIFECYCLE_DAYS = int(os.getenv("GCS_LIFECYCLE_DAYS", "7"))

# Temporary file storage prefix
GCS_TEMP_PREFIX = "temp"

# ============================================
# Google Cloud Speech-to-Text Configuration  
# ============================================

# Default language for Japanese presentations
SPEECH_LANGUAGE_CODE = os.getenv("SPEECH_LANGUAGE_CODE", "ja-JP")

# Model selection
# Per plan: "Set the model to 'chirp' for best accuracy"
SPEECH_MODEL = os.getenv("SPEECH_MODEL", "chirp")  # Options: "chirp", "latest_long", "latest_short"

# Recognition configuration
SPEECH_CONFIG = {
    "language_code": SPEECH_LANGUAGE_CODE,
    "model": SPEECH_MODEL,
    "enable_automatic_punctuation": True,  # Add punctuation marks
    "enable_word_time_offsets": True,      # Critical for slide synchronization
    "enable_word_confidence": True,        # Word-level confidence scores
    "audio_channel_count": 1,              # Mono audio
    "sample_rate_hertz": 16000,            # 16kHz sample rate (minimum)
}

# Streaming configuration (Phase 3)
STREAMING_CONFIG = {
    "interim_results": True,               # Get partial results
    "single_utterance": False,             # Continuous speech
    "max_session_duration": 270,           # 4.5 minutes (before timeout at 5 min)
}

# Speaker diarization (optional, adds cost)
ENABLE_SPEAKER_DIARIZATION = os.getenv("ENABLE_SPEAKER_DIARIZATION", "false").lower() == "true"
if ENABLE_SPEAKER_DIARIZATION:
    SPEECH_CONFIG["diarization_config"] = {
        "enable_speaker_diarization": True,
        "min_speaker_count": 1,
        "max_speaker_count": 4
    }

# ============================================
# Google Cloud Translation Configuration
# ============================================

# Target languages for translation
TRANSLATION_TARGET_LANGUAGES = ["en", "vi"]  # English, Vietnamese

# ============================================
# Processing Configuration
# ============================================

# Temporary directory for file transfers
TEMP_DIR = os.getenv("TEMP_DIR", "/tmp/speech_processing")

# Maximum retries for network operations
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Timeouts
DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "300"))  # 5 minutes
UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", "300"))      # 5 minutes

# ============================================
# Database Configuration
# ============================================

DATABASE_FILE = os.getenv("DATABASE_FILE", "database.json")

# ============================================
# Logging Configuration
# ============================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# ============================================
# Cost Tracking
# ============================================

# Google Cloud Speech-to-Text pricing (as of 2024)
# Chirp model: $0.016 per minute = $0.96 per hour
CHIRP_COST_PER_MINUTE = 0.016

# Standard model: $0.006 per minute
STANDARD_COST_PER_MINUTE = 0.006

# Streaming: $0.01 per minute
STREAMING_COST_PER_MINUTE = 0.01

# Translation: $20 per 1M characters
TRANSLATION_COST_PER_CHAR = 20 / 1_000_000

# ============================================
# Validation
# ============================================

def validate_config():
    """Validate all required configuration is present"""
    required_vars = {
        "GCP_PROJECT_ID": GCP_PROJECT_ID,
        "GCP_SERVICE_ACCOUNT_KEY": GCP_SERVICE_ACCOUNT_KEY,
    }
    
    missing = [k for k, v in required_vars.items() if not v]
    
    if missing:
        raise ValueError(
            f"Missing required configuration: {', '.join(missing)}\n"
            f"Please update your .env file"
        )
    
    return True

# Validate on import
validate_config()
