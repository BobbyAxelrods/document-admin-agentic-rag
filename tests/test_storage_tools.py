import unittest
from unittest.mock import MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

sys.modules['google'] = MagicMock()
sys.modules['google.cloud'] = MagicMock()
sys.modules['google.cloud.storage'] = MagicMock()
sys.modules['google.adk'] = MagicMock()
sys.modules['google.adk.tools'] = MagicMock()
sys.modules['google.adk.agents'] = MagicMock()
sys.modules['google.api_core'] = MagicMock()

# Define dummy exceptions first
class DummyConflict(Exception):
    pass

class DummyForbidden(Exception):
    pass

class DummyBadRequest(Exception):
    pass

# Setup exceptions mock with actual classes
mock_exceptions = MagicMock()
mock_exceptions.Conflict = DummyConflict
mock_exceptions.Forbidden = DummyForbidden
mock_exceptions.BadRequest = DummyBadRequest
mock_exceptions.GoogleAPIError = Exception
sys.modules['google.api_core.exceptions'] = mock_exceptions

sys.modules['google.auth'] = MagicMock()
sys.modules['vertexai'] = MagicMock()
sys.modules['vertexai.preview'] = MagicMock()
sys.modules['google.cloud.aiplatform'] = MagicMock()
sys.modules['google.adk.models.lite_llm'] = MagicMock()

from rag.tools.storage import storage_tools

# We don't need to patch storage_tools.Conflict etc anymore because
# they were imported as the dummy classes thanks to our mock setup.

class TestStorageTools(unittest.TestCase):
    def setUp(self):
        storage_tools.client = MagicMock()
        self.mock_client = storage_tools.client
        self.mock_client.project = "test-project"

    def test_create_gcs_bucket_success(self):
        mock_bucket = MagicMock()
        mock_bucket.self_link = "https://storage.googleapis.com/test-bucket"
        mock_bucket.location = "US"
        mock_bucket.storage_class = "STANDARD"
        self.mock_client.create_bucket.return_value = mock_bucket
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.create_gcs_bucket(tool_context, "my-bucket")
        self.assertEqual(result['status'], 'success')
        self.assertIn('test-project', result['bucket_name'])
        self.mock_client.create_bucket.assert_called_once()

    def test_create_gcs_bucket_conflict(self):
        self.mock_client.create_bucket.side_effect = DummyConflict("exists")
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.create_gcs_bucket(tool_context, "my-bucket")
        self.assertEqual(result['status'], 'exists')

    def test_create_gcs_bucket_forbidden_global_name_conflict(self):
        self.mock_client.create_bucket.side_effect = DummyForbidden("already exists")
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.create_gcs_bucket(tool_context, "my-bucket")
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'global_name_conflict')
        self.assertIn('suggestion', result)

    def test_create_gcs_bucket_forbidden_permission_denied(self):
        self.mock_client.create_bucket.side_effect = DummyForbidden("permission denied")
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.create_gcs_bucket(tool_context, "my-bucket")
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'permission_denied')

    def test_create_gcs_bucket_bad_request(self):
        self.mock_client.create_bucket.side_effect = DummyBadRequest("invalid")
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.create_gcs_bucket(tool_context, "bad")
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'invalid_request')

    def test_create_gcs_bucket_unknown(self):
        self.mock_client.create_bucket.side_effect = Exception("boom")
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.create_gcs_bucket(tool_context, "any")
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error_type'], 'unknown')

    def test_list_gcs_buckets(self):
        b1 = MagicMock()
        b1.name = "bucket-1"
        self.mock_client.list_buckets.return_value = [b1]
        result = storage_tools.list_gcs_buckets(MagicMock())
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['buckets'][0], 'bucket-1')

    def test_list_gcs_buckets_client_not_initialized(self):
        storage_tools.client = None
        result = storage_tools.list_gcs_buckets(MagicMock())
        self.assertEqual(result['status'], 'error')

    def test_list_blobs_bucket_not_exists(self):
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = False
        self.mock_client.bucket.return_value = mock_bucket
        result = storage_tools.list_blobs(MagicMock(), "bucket-1")
        self.assertEqual(result['status'], 'error')

    def test_list_blobs_with_prefix(self):
        mock_bucket = MagicMock()
        mock_bucket.exists.return_value = True
        blob = MagicMock()
        blob.name = "dir/file1.txt"
        mock_bucket.list_blobs.return_value = [blob]
        self.mock_client.bucket.return_value = mock_bucket
        result = storage_tools.list_blobs(MagicMock(), "bucket-1", prefix="dir/")
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['files'][0], "dir/file1.txt")

    def test_upload_file_to_gcs_success(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        self.mock_client.bucket.return_value = mock_bucket
        tool_context = MagicMock()
        tool_context.state = {}
        result = storage_tools.upload_file_to_gcs(tool_context, "bucket-1", "local.txt", "remote.txt")
        self.assertEqual(result['status'], 'success')
        mock_blob.upload_from_filename.assert_called_once_with("local.txt")
        self.assertEqual(result['gcs_uri'], "gs://bucket-1/remote.txt")

    def test_upload_file_to_gcs_error(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.upload_from_filename.side_effect = Exception("fail")
        mock_bucket.blob.return_value = mock_blob
        self.mock_client.bucket.return_value = mock_bucket
        result = storage_tools.upload_file_to_gcs(MagicMock(), "bucket-1", "local.txt", "remote.txt")
        self.assertEqual(result['status'], 'error')

    def test_move_gcs_file_success(self):
        source_bucket = MagicMock()
        source_blob = MagicMock()
        dest_bucket = MagicMock()
        source_bucket.blob.return_value = source_blob
        self.mock_client.bucket.side_effect = [source_bucket, dest_bucket]
        result = storage_tools.move_gcs_file(MagicMock(), "src-b", "a.txt", "dst-b", "b.txt")
        self.assertEqual(result['status'], 'success')
        source_bucket.copy_blob.assert_called_once()
        source_blob.delete.assert_called_once()

    def test_move_gcs_file_error(self):
        source_bucket = MagicMock()
        source_blob = MagicMock()
        dest_bucket = MagicMock()
        source_bucket.blob.return_value = source_blob
        source_bucket.copy_blob.side_effect = Exception("copy-fail")
        self.mock_client.bucket.side_effect = [source_bucket, dest_bucket]
        result = storage_tools.move_gcs_file(MagicMock(), "src-b", "a.txt", "dst-b", "b.txt")
        self.assertEqual(result['status'], 'error')

    def test_delete_gcs_file_success(self):
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        self.mock_client.bucket.return_value = mock_bucket
        result = storage_tools.delete_gcs_file(MagicMock(), "bucket-1", "file.txt")
        self.assertEqual(result['status'], 'success')
        mock_blob.delete.assert_called_once()

    def test_delete_gcs_bucket_force_true(self):
        tool_context = MagicMock()
        tool_context.state = {"last_bucket_name": "bucket-1"}
        mock_bucket = MagicMock()
        blob1 = MagicMock()
        blob2 = MagicMock()
        mock_bucket.list_blobs.return_value = [blob1, blob2]
        self.mock_client.bucket.return_value = mock_bucket
        result = storage_tools.delete_gcs_bucket(tool_context, "bucket-1", force=True)
        self.assertEqual(result['status'], 'success')
        blob1.delete.assert_called_once()
        blob2.delete.assert_called_once()
        mock_bucket.delete.assert_called_once()
        self.assertNotIn("last_bucket_name", tool_context.state)

    def test_delete_gcs_bucket_no_force(self):
        tool_context = MagicMock()
        tool_context.state = {}
        mock_bucket = MagicMock()
        self.mock_client.bucket.return_value = mock_bucket
        result = storage_tools.delete_gcs_bucket(tool_context, "bucket-1", force=False)
        self.assertEqual(result['status'], 'success')
        mock_bucket.delete.assert_called_once()

if __name__ == '__main__':
    unittest.main()
