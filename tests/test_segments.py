import unittest
from unittest.mock import patch

from provider.dify_knowledge_api import DifyKnowledgeApiError, DifyKnowledgeClient
from provider.dify_knowledge_utils import (
    build_list_segments_params,
    normalize_segment_list_response,
    normalize_segment_response,
    select_document_id,
    select_segment_id,
)


class SegmentToolsTestCase(unittest.TestCase):
    def test_required_ids_reject_blank_values(self) -> None:
        for selector, key in ((select_document_id, "document_id"), (select_segment_id, "segment_id")):
            for value in (None, "", "  "):
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, key):
                    selector({key: value})
            self.assertEqual(selector({key: " id-1 "}), "id-1")

    def test_pagination_defaults_and_status_filters(self) -> None:
        self.assertEqual(build_list_segments_params({}), {"page": 1, "limit": 20})
        for status in ("completed,error", '["completed", "error"]', ["completed", "error"]):
            with self.subTest(status=status):
                self.assertEqual(
                    build_list_segments_params({"page": "2", "limit": 100.0, "keyword": " guide ", "status": status}),
                    {"page": 2, "limit": 100, "keyword": "guide", "status": ["completed", "error"]},
                )

    def test_invalid_pagination_is_rejected(self) -> None:
        for key, values in (("page", [0, -1, 1.5, "bad", True, float("inf")]), ("limit", [0, 101, 1.5])):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    build_list_segments_params({key: value})

    def test_list_preserves_content_qa_and_pagination(self) -> None:
        segment = {
            "id": "s1", "document_id": "doc1", "position": 3,
            "content": "What is the refund policy?", "answer": "Within 30 days.",
            "status": "completed", "enabled": False, "error": None,
            "keywords": ["refund"], "attachments": [{"id": "file1"}],
            "child_chunks": [{"id": "child1", "content": "Exceptions apply."}],
        }
        response = {"data": [segment], "doc_form": "qa_model", "page": 2, "limit": 1, "total": 3, "has_more": True}
        result = normalize_segment_list_response(response, "kb1", "doc1")
        self.assertEqual((result["page"], result["limit"], result["total"], result["has_more"], result["count"]), (2, 1, 3, True, 1))
        item = result["result"][0]
        self.assertEqual(item["content"], segment["content"])
        self.assertEqual(item["answer"], segment["answer"])
        self.assertEqual(item["segment_id"], "s1")
        self.assertEqual(item["dataset_id"], "kb1")
        self.assertFalse(item["enabled"])
        self.assertEqual(item["child_chunks"], segment["child_chunks"])
        self.assertEqual(item["attachments"], segment["attachments"])
        self.assertNotIn("dataset_id", segment)

    def test_empty_document_list(self) -> None:
        result = normalize_segment_list_response({"data": [], "total": 0, "has_more": False}, "kb1", "doc1")
        self.assertEqual(result["result"], [])
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["has_more"])

    def test_detail_unwraps_data_and_preserves_optional_fields(self) -> None:
        result = normalize_segment_response({"data": {"id": "s1", "content": "Text", "keywords": None, "summary": "Summary"}, "doc_form": "hierarchical_model"}, "kb1", "doc1")
        self.assertEqual(result["doc_form"], "hierarchical_model")
        self.assertEqual(result["result"]["segment_id"], "s1")
        self.assertEqual(result["result"]["summary"], "Summary")
        self.assertEqual(result["result"]["keywords"], [])
        self.assertEqual(result["result"]["attachments"], [])

    @patch("provider.dify_knowledge_api.requests.request")
    def test_list_request_encodes_multiple_status_values(self, request) -> None:
        request.return_value.status_code = 200
        request.return_value.json.return_value = {"data": []}
        client = DifyKnowledgeClient("https://dify.example", "test-key")
        client.list_segments("kb1", "doc1", page=2, limit=10, keyword="refund", status=["completed", "error"])
        kwargs = request.call_args.kwargs
        self.assertEqual(kwargs["method"], "GET")
        self.assertEqual(kwargs["url"], "https://dify.example/v1/datasets/kb1/documents/doc1/segments")
        self.assertEqual(kwargs["params"], {"page": 2, "limit": 10, "keyword": "refund", "status": ["completed", "error"]})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")

    @patch("provider.dify_knowledge_api.requests.request")
    def test_detail_request_and_missing_segment_error(self, request) -> None:
        request.return_value.status_code = 404
        request.return_value.json.return_value = {"code": "not_found", "message": "Segment not found."}
        client = DifyKnowledgeClient("https://dify.example/v1", "test-key")
        with self.assertRaisesRegex(DifyKnowledgeApiError, "HTTP 404.*Segment not found"):
            client.get_segment("kb1", "doc1", "missing")
        self.assertEqual(request.call_args.kwargs["url"], "https://dify.example/v1/datasets/kb1/documents/doc1/segments/missing")


if __name__ == "__main__":
    unittest.main()
