# Phase 1 Setup Guide

## Foundation and Setup (Week 1-2)

### Week 1: Google Cloud Platform Setup

#### Step 1: Create GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Project name: `speech-processing-prod`
4. Click "Create"

#### Step 2: Enable Required APIs

```bash
# Enable Speech-to-Text API
gcloud services enable speech.googleapis.com

# Enable Translation API
gcloud services enable translate.googleapis.com

# Enable Cloud Storage API
gcloud services enable storage-api.googleapis.com
```

Or enable via Console:

- Go to "APIs & Services" → "Library"
- Search and enable:
  - Cloud Speech-to-Text API
  - Cloud Translation API
  - Cloud Storage API

#### Step 3: Create Service Account

```bash
# Create service account
gcloud iam service-accounts create speech-processing-sa \
    --display-name="Speech Processing Service Account"

# Grant necessary roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:speech-processing-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/speech.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:speech-processing-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/cloudtranslate.admin"

gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:speech-processing-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"

# Download JSON key
gcloud iam service-accounts keys create ~/speech-processing-key.json \
    --iam-account=speech-processing-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Or via Console:

- Go to "IAM & Admin" → "Service Accounts"
- Click "Create Service Account"
- Name: `speech-processing-sa`
- Grant roles:
  - Speech-to-Text Admin
  - Cloud Translation Admin
  - Storage Admin
- Click "Done"
- Click on the service account → "Keys" tab → "Add Key" → "Create new key" → JSON
- Download the JSON file

**IMPORTANT**: Store the JSON key securely! Never commit to Git!

#### Step 4: Create GCS Bucket

```bash
# Create bucket in Singapore region (close to AWS S3)
gsutil mb -l asia-southeast1 gs://speech-processing-intermediate

# Set lifecycle policy (auto-delete after 7 days)
cat > lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 7}
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://speech-processing-intermediate
```

Or via Console:

- Go to "Cloud Storage" → "Buckets"
- Click "Create Bucket"
- Name: `speech-processing-intermediate`
- Location: Region → `asia-southeast1` (Singapore)
- Click "Create"
- Go to bucket → "Lifecycle" tab → "Add a rule"
- Action: Delete object
- Condition: Age → 7 days
- Click "Create"

#### Step 5: Update .env File

```bash
# Copy example
cp .env.example .env

# Edit .env
nano .env
```

Update these values:

```env
GCP_PROJECT_ID=speech-processing-prod
GCP_SERVICE_ACCOUNT_KEY=/path/to/downloaded/speech-processing-key.json
GCS_BUCKET_NAME=speech-processing-intermediate
GCS_REGION=asia-southeast1
```

#### Step 6: Install Python Dependencies

```bash
# Install Google Cloud libraries
pip install google-cloud-speech==2.21.0
pip install google-cloud-storage==2.10.0
pip install google-cloud-translate==3.12.0

# Update requirements.txt
pip freeze > requirements.txt
```

### Week 2: Testing and Validation

#### Test 1: GCS Connection

```bash
python3 -c "
from src.google_cloud.gcs_storage import GCSStorage
from config.google_cloud_config import GCS_BUCKET_NAME, GCP_SERVICE_ACCOUNT_KEY

gcs = GCSStorage(GCS_BUCKET_NAME, GCP_SERVICE_ACCOUNT_KEY)
print('✅ GCS connection successful!')
"
```

#### Test 2: Run Integration Tests

```bash
# Run all Phase 1 tests
python3 tests/test_phase1_integration.py
```

Expected output:

```
============================================================
PHASE 1 INTEGRATION TESTS
Foundation and Setup (Week 1-2)
============================================================

test_01_upload_file ... ✅ Upload test passed
test_02_file_exists ... ✅ File exists test passed
test_03_download_file ... ✅ Download test passed
test_04_list_files ... ✅ List files test passed
test_05_delete_file ... ✅ Delete test passed
test_01_transfer_file ... ✅ Transfer test passed
test_02_transfer_with_integrity_check ... ✅ Integrity check test passed
test_03_transfer_nonexistent_file ... ✅ Nonexistent file test passed
test_presentation_workflow ... ✅ End-to-end workflow passed

============================================================
PHASE 1 TEST SUMMARY
============================================================
Tests run: 9
Successes: 9
Failures: 0
Errors: 0

✅ ALL PHASE 1 TESTS PASSED!
```

### Phase 1 Success Metrics

Verify these metrics are met:

- ✅ **Authentication**: Successfully authenticate with Google Cloud using service accounts
- ✅ **File Transfer**: Transfer 100MB file from S3 to GCS in < 30 seconds
- ✅ **Format Support**: Handle MP3, WAV, M4A formats
- ✅ **Error Handling**: Automatic retry on transient network errors
- ✅ **Integrity**: File size verification after transfer
- ✅ **Cleanup**: Successful cleanup of temporary files

### Troubleshooting

#### Error: "Cannot initialize GCS"

Check:

1. Service account JSON file path is correct in .env
2. File has proper permissions (readable)
3. Project ID matches the one in GCP Console

```bash
# Verify credentials
python3 -c "
import os
from config.google_cloud_config import GCP_SERVICE_ACCOUNT_KEY
print(f'Key file: {GCP_SERVICE_ACCOUNT_KEY}')
print(f'Exists: {os.path.exists(GCP_SERVICE_ACCOUNT_KEY)}')
"
```

#### Error: "Bucket not found"

Create the bucket:

```bash
gsutil mb -l asia-southeast1 gs://speech-processing-intermediate
```

#### Error: "Permission denied"

Grant required roles to service account:

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:YOUR_SA@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.admin"
```

### Next Steps

Once Phase 1 tests pass, you're ready for:

**Phase 2: File-Based Processing Pipeline (Week 3-5)**

- Implement Google Cloud Speech-to-Text integration
- Build result processing and storage
- Handle edge cases and quality assurance

Continue to Phase 2 setup guide when ready.
