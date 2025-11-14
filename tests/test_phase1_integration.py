"""
Integration tests for Phase 1: Foundation and Setup (GCS Only)
Tests GCS storage operations without S3 dependencies.
"""
import os
import sys
import unittest
import tempfile
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.google_cloud.gcs_storage import GCSStorage
from config.google_cloud_config import (
    GCS_BUCKET_NAME,
    GCP_SERVICE_ACCOUNT_KEY
)


class TestGCSStorage(unittest.TestCase):
    """Test Google Cloud Storage operations"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize GCS client once for all tests"""
        try:
            cls.gcs = GCSStorage(
                bucket_name=GCS_BUCKET_NAME,
                credentials_path=GCP_SERVICE_ACCOUNT_KEY
            )
            print("\n✅ GCS client initialized")
        except Exception as e:
            raise unittest.SkipTest(f"Cannot initialize GCS: {e}")
    
    def setUp(self):
        """Create a test file before each test"""
        self.test_content = f"Test file created at {time.time()}"
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
        self.temp_file.write(self.test_content)
        self.temp_file.close()
        
        self.test_gcs_key = f"test/integration/{int(time.time())}/test.txt"
    
    def tearDown(self):
        """Cleanup after each test"""
        # Delete test file from GCS
        if hasattr(self, 'test_gcs_key'):
            try:
                self.gcs.delete_file(self.test_gcs_key)
            except:
                pass
        
        # Delete local temp file
        if hasattr(self, 'temp_file'):
            try:
                os.unlink(self.temp_file.name)
            except:
                pass
    
    def test_1_upload_file(self):
        """Test uploading a file to GCS"""
        print("\nTest 1: Upload file to GCS")
        
        result = self.gcs.upload_file(
            local_file_path=self.temp_file.name,
            gcs_key=self.test_gcs_key
        )
        
        self.assertTrue(result["success"], f"Upload failed: {result.get('error')}")
        gcs_uri = result["gcs_uri"]
        self.assertTrue(gcs_uri.startswith("gs://"))
        
        print(f"✅ Upload test passed: {gcs_uri}")
    
    def test_2_file_exists(self):
        """Test checking if file exists in GCS"""
        print("\nTest 2: Check file exists")
        
        # Upload first
        self.gcs.upload_file(
            local_file_path=self.temp_file.name,
            gcs_key=self.test_gcs_key
        )
        
        # Check exists
        exists = self.gcs.file_exists(self.test_gcs_key)
        self.assertTrue(exists)
        
        # Check non-existent file
        not_exists = self.gcs.file_exists("non/existent/file.txt")
        self.assertFalse(not_exists)
        
        print("✅ File exists test passed")
    
    def test_3_download_file(self):
        """Test downloading a file from GCS"""
        print("\nTest 3: Download file from GCS")
        
        # Upload first
        self.gcs.upload_file(
            local_file_path=self.temp_file.name,
            gcs_key=self.test_gcs_key
        )
        
        # Download
        download_path = tempfile.mktemp(suffix='.txt')
        result = self.gcs.download_file(
            gcs_key=self.test_gcs_key,
            local_file_path=download_path
        )
        
        self.assertTrue(result["success"], f"Download failed: {result.get('error')}")
        downloaded_file = result["local_path"]
        self.assertTrue(os.path.exists(downloaded_file))
        
        # Verify content
        with open(downloaded_file, 'r') as f:
            content = f.read()
        
        self.assertEqual(content, self.test_content)
        
        # Cleanup download
        os.unlink(downloaded_file)
        
        print("✅ Download test passed")
    
    def test_4_list_files(self):
        """Test listing files in GCS"""
        print("\nTest 4: List files in GCS")
        
        # Upload multiple files
        prefix = f"test/list/{int(time.time())}"
        files = []
        
        for i in range(3):
            gcs_key = f"{prefix}/file_{i}.txt"
            self.gcs.upload_file(
                local_file_path=self.temp_file.name,
                gcs_key=gcs_key
            )
            files.append(gcs_key)
        
        # List files
        listed = self.gcs.list_files(prefix=prefix)
        
        self.assertGreaterEqual(len(listed), 3)
        
        # Cleanup
        for gcs_key in files:
            self.gcs.delete_file(gcs_key)
        
        print(f"✅ List test passed: found {len(listed)} files")
    
    def test_5_delete_file(self):
        """Test deleting a file from GCS"""
        print("\nTest 5: Delete file from GCS")
        
        # Upload first
        self.gcs.upload_file(
            local_file_path=self.temp_file.name,
            gcs_key=self.test_gcs_key
        )
        
        # Verify exists
        self.assertTrue(self.gcs.file_exists(self.test_gcs_key))
        
        # Delete
        self.gcs.delete_file(self.test_gcs_key)
        
        # Verify deleted
        self.assertFalse(self.gcs.file_exists(self.test_gcs_key))
        
        print("✅ Delete test passed")
    
    def test_6_cleanup_presentation(self):
        """Test cleaning up all files for a presentation"""
        print("\nTest 6: Cleanup presentation files")
        
        # Upload multiple files for a presentation (in temp/ folder as per GCS implementation)
        presentation_id = f"pres_test_{int(time.time())}"
        files = []
        
        for file_type in ['audio', 'slides', 'transcripts']:
            gcs_key = f"temp/{presentation_id}/{file_type}/test.txt"
            self.gcs.upload_file(
                local_file_path=self.temp_file.name,
                gcs_key=gcs_key
            )
            files.append(gcs_key)
        
        # Verify files exist
        for gcs_key in files:
            self.assertTrue(self.gcs.file_exists(gcs_key))
        
        # Cleanup presentation
        result = self.gcs.cleanup_presentation(presentation_id)
        
        self.assertTrue(result["success"], f"Cleanup failed: {result.get('error')}")
        deleted_count = result["deleted_count"]
        self.assertGreaterEqual(deleted_count, 3)
        
        # Verify files deleted
        for gcs_key in files:
            self.assertFalse(self.gcs.file_exists(gcs_key))
        
        print(f"✅ Cleanup test passed: {deleted_count} files deleted")


def run_tests():
    """Run all Phase 1 integration tests"""
    print("\n" + "="*70)
    print(" PHASE 1 INTEGRATION TESTS (GCS Only)")
    print("="*70)
    print("\nTesting Google Cloud Storage operations...")
    print(f"GCS Bucket: {GCS_BUCKET_NAME}")
    print("="*70)
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestGCSStorage)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*70)
    print(" TEST SUMMARY")
    print("="*70)
    
    if result.wasSuccessful():
        print("✅ ALL PHASE 1 TESTS PASSED!")
        print(f"\nTests run: {result.testsRun}")
        print("Phase 1 Deliverables Verified:")
        print("  ✅ GCS upload/download working")
        print("  ✅ File existence checks working")
        print("  ✅ File listing working")
        print("  ✅ File deletion working")
        print("  ✅ Presentation cleanup working")
    else:
        print("❌ SOME TESTS FAILED")
        print(f"\nTests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
    
    print("="*70)
    
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    exit(run_tests())
