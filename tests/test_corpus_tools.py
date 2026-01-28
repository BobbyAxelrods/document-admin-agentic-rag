import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

sys.modules['vertexai'] = MagicMock()
sys.modules['vertexai.preview'] = MagicMock()
sys.modules['vertexai.preview.rag'] = MagicMock()

from rag.tools.corpus import corpus_tools

class TestCorpusTools(unittest.TestCase):
    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_create_corpus(self, mock_rag):
        mock_corpus = MagicMock()
        mock_corpus.name = "projects/p/locations/l/ragCorpora/123"
        mock_rag.create_corpus.return_value = mock_corpus
        result = corpus_tools.create_corpus("test-corpus", "desc")
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['corpus_id'], '123')
        mock_rag.create_corpus.assert_called_once()

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_update_corpus(self, mock_rag):
        updated = MagicMock()
        updated.name = "projects/p/locations/l/ragCorpora/1"
        updated.display_name = "new"
        updated.description = "desc"
        mock_rag.update_corpus.return_value = updated
        result = corpus_tools.update_corpus("1", display_name="new", description="desc")
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['corpus_id'], '1')
        self.assertEqual(result['display_name'], 'new')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_list_corpora(self, mock_rag):
        c1 = MagicMock()
        c1.name = "projects/p/locations/l/ragCorpora/1"
        c1.display_name = "c1"
        mock_rag.list_corpora.return_value = [c1]
        result = corpus_tools.list_corpora()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['corpora']), 1)
        self.assertEqual(result['corpora'][0]['id'], '1')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_get_corpus(self, mock_rag):
        c1 = MagicMock()
        c1.name = "projects/p/locations/l/ragCorpora/1"
        c1.display_name = "c1"
        mock_rag.get_corpus.return_value = c1
        mock_rag.list_files.return_value = iter([])
        result = corpus_tools.get_corpus("1")
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['corpus']['id'], '1')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_delete_corpus(self, mock_rag):
        result = corpus_tools.delete_corpus("1")
        self.assertEqual(result['status'], 'success')
        mock_rag.delete_corpus.assert_called_once()

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_import_files(self, mock_rag):
        response = MagicMock()
        response.imported_rag_files_count = 5
        mock_rag.import_files.return_value = response
        result = corpus_tools.import_files("1", ["gs://bucket/file.pdf"])
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['imported_count'], 5)
        mock_rag.import_files.assert_called_once()

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_list_files(self, mock_rag):
        f1 = MagicMock()
        f1.name = "projects/p/locations/l/ragCorpora/1/ragFiles/f1"
        f1.display_name = "file1.pdf"
        mock_rag.list_files.return_value = [f1]
        result = corpus_tools.list_files("1")
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['files']), 1)
        self.assertEqual(result['files'][0]['id'], 'f1')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_get_file(self, mock_rag):
        f = MagicMock()
        f.name = "projects/p/locations/l/ragCorpora/1/ragFiles/f1"
        f.display_name = "file1.pdf"
        mock_rag.get_file.return_value = f
        result = corpus_tools.get_file("1", "f1")
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['file']['id'], 'f1')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_delete_file_from_corpus(self, mock_rag):
        result = corpus_tools.delete_file_from_corpus("1", "f1")
        self.assertEqual(result['status'], 'success')
        mock_rag.delete_file.assert_called_once()

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_query_corpus(self, mock_rag):
        ctx = MagicMock()
        ctx.text = "t"
        ctx.source_uri = "s"
        ctx.distance = 0.1
        contexts_container = MagicMock()
        contexts_container.contexts = [ctx]
        resp = MagicMock()
        resp.contexts = contexts_container
        mock_rag.retrieval_query.return_value = resp
        result = corpus_tools.query_corpus("1", "q", similarity_top_k=3, vector_distance_threshold=0.5)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['text'], 't')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_query_corpus_error(self, mock_rag):
        mock_rag.retrieval_query.side_effect = Exception("fail")
        result = corpus_tools.query_corpus("1", "q")
        self.assertEqual(result['status'], 'error')

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_get_corpus_id_by_display_name(self, mock_rag):
        c1 = MagicMock()
        c1.name = "projects/p/locations/l/ragCorpora/1"
        c1.display_name = "target"
        mock_rag.list_corpora.return_value = [c1]
        corpus_id = corpus_tools.get_corpus_id_by_display_name("target")
        self.assertEqual(corpus_id, "1")
        corpus_id_none = corpus_tools.get_corpus_id_by_display_name("missing")
        self.assertIsNone(corpus_id_none)

    @patch('rag.tools.corpus.corpus_tools.rag')
    def test_get_file_id_by_name(self, mock_rag):
        f1 = MagicMock()
        f1.name = "projects/p/locations/l/ragCorpora/1/ragFiles/f1"
        f1.display_name = "file1.pdf"
        f2 = MagicMock()
        f2.name = "projects/p/locations/l/ragCorpora/1/ragFiles/f2"
        f2.display_name = "folder/file2.pdf"
        mock_rag.list_files.return_value = [f1, f2]
        fid1 = corpus_tools.get_file_id_by_name("1", "file1.pdf")
        self.assertEqual(fid1, "f1")
        fid2 = corpus_tools.get_file_id_by_name("1", "file2.pdf")
        self.assertEqual(fid2, "f2")

if __name__ == '__main__':
    unittest.main()
