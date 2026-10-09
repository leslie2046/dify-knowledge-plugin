import unittest
from unittest.mock import Mock, patch

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.knowledge_operations import document_payload, invoke_operation, metadata_conditions, retrieve_multiple, retrieve_payload


class KnowledgeOperationsTestCase(unittest.TestCase):
    def setUp(self):
        self.saved = {
            "search_method": "hybrid_search", "top_k": 5, "reranking_enable": True,
            "reranking_mode": "reranking_model",
            "reranking_model": {"reranking_provider_name": "provider", "reranking_model_name": "reranker"},
            "score_threshold_enabled": False, "score_threshold": 0.4,
            "weights": {"weight_type": "customized", "vector_setting": {"vector_weight": 0.7, "embedding_model_name": "embed"}, "keyword_setting": {"keyword_weight": 0.3}},
        }
        self.client = Mock()
        self.client.get_dataset.return_value = {"provider": "vendor", "retrieval_model_dict": self.saved}

    def test_plain_retrieval_does_not_fetch_configuration(self):
        self.assertEqual(retrieve_payload(self.client, "kb", {"query": "hello"}), {"query": "hello"})
        self.client.get_dataset.assert_not_called()

    def test_top_k_preserves_hybrid_reranking_weights_and_disabled_threshold(self):
        model = retrieve_payload(self.client, "kb", {"query": "hello", "top_k": 8})["retrieval_model"]
        self.assertEqual(model, dict(self.saved, top_k=8))
        self.assertEqual(self.saved["top_k"], 5)

    def test_explicit_disable_wins_over_threshold_and_saved_reranking(self):
        model = retrieve_payload(self.client, "kb", {"query": "hello", "score_threshold": 0.8, "score_threshold_enabled": False, "reranking_enable": False})["retrieval_model"]
        self.assertFalse(model["score_threshold_enabled"])
        self.assertFalse(model["reranking_enable"])
        self.assertNotIn("reranking_model", model)

    def test_changing_method_removes_saved_weights(self):
        model = retrieve_payload(self.client, "kb", {"query": "hello", "search_method": "semantic_search"})["retrieval_model"]
        self.assertEqual(model["search_method"], "semantic_search")
        self.assertNotIn("weights", model)

    def test_metadata_filter_is_sent_before_retrieval(self):
        filters = {"logical_operator": "and", "conditions": [{"name": "version", "comparison_operator": ">=", "value": 2}]}
        model = retrieve_payload(self.client, "kb", {"query": "hello", "metadata_filtering_conditions": filters})["retrieval_model"]
        self.assertEqual(model["metadata_filtering_conditions"]["conditions"][0]["comparison_operator"], "≥")
        self.assertEqual(model["top_k"], 5)
        self.assertEqual(filters["conditions"][0]["comparison_operator"], ">=")

    def test_bad_filter_and_invalid_limits_fail_before_network(self):
        for parameters in ({"metadata_filtering_conditions": "[]"}, {"top_k": 2.5}, {"score_threshold": 1.1}, {"query": "x" * 251}):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                retrieve_payload(self.client, "kb", {"query": "hello", **parameters})
        self.client.get_dataset.assert_not_called()
        for condition in ({"name": "v", "comparison_operator": "in", "value": "bad"}, {"name": "v", "comparison_operator": ">", "value": "2"}):
            with self.assertRaises(ValueError):
                metadata_conditions({"conditions": [condition]})

    def test_external_uses_external_configuration(self):
        self.client.get_dataset.return_value = {"provider": "external", "external_retrieval_model": {"top_k": 3, "score_threshold": 0.3, "score_threshold_enabled": True}}
        payload = retrieve_payload(self.client, "kb", {"query": "hello", "top_k": 8})
        self.assertEqual(payload["external_retrieval_model"], {"top_k": 8, "score_threshold": 0.3, "score_threshold_enabled": True})
        self.assertNotIn("retrieval_model", payload)
        with self.assertRaises(ValueError):
            retrieve_payload(self.client, "kb", {"query": "hello", "search_method": "semantic_search"})

    def test_creation_and_update_payloads(self):
        self.assertEqual(document_payload({"name": "FAQ", "text": "  Text\n "}), {"name": "FAQ", "text": "  Text\n ", "process_rule": {"mode": "automatic"}})
        self.assertEqual(document_payload({"name": "New name"}, update=True), {"name": "New name"})
        for parameters in ({}, {"text": "new"}, {"process_rule": "bad"}):
            with self.assertRaises(ValueError):
                document_payload(parameters, update=True)
        with self.assertRaises(ValueError):
            document_payload({"name": "FAQ", "text": "Text", "doc_form": "hierarchical_model"})

    def test_create_and_update_return_batch(self):
        response = {"document": {"id": "doc1", "indexing_status": "waiting"}, "batch": "batch1"}
        self.client.create_document_by_text.return_value = response
        self.client.update_document_by_text.return_value = response
        for op in ("create_document_by_text", "update_document_by_text"):
            result = invoke_operation(self.client, op, {"dataset_id": "kb", "document_id": "doc1", "name": "FAQ", "text": "Text"})
            self.assertEqual(result["batch"], "batch1")
            self.assertEqual(result["document_id"], "doc1")
            self.assertEqual(result["result"]["indexing_status"], "waiting")

    def test_indexing_distinguishes_processing_success_failure_and_empty(self):
        for states, completed, finished, errors in [([], False, False, False), (["indexing"], False, False, False), (["completed"], True, True, False), (["completed", "error"], False, True, True)]:
            with self.subTest(states=states):
                self.client.get_indexing_status.return_value = {"data": [{"indexing_status": state} for state in states]}
                result = invoke_operation(self.client, "get_indexing_status", {"dataset_id": "kb", "batch": "batch1"})
                self.assertEqual((result["completed"], result["finished"], result["has_errors"]), (completed, finished, errors))

    def test_metadata_tags_and_dataset_details(self):
        self.client.list_metadata_fields.return_value = {"doc_metadata": [{"name": "department", "type": "string"}], "built_in_field_enabled": True}
        result = invoke_operation(self.client, "list_metadata_fields", {"dataset_id": "kb"})
        self.assertEqual(result["count"], 1)
        self.assertTrue(result["built_in_field_enabled"])
        self.client.list_tags.return_value = [{"id": "tag1", "name": "docs"}]
        self.assertEqual(invoke_operation(self.client, "list_tags", {})["result"][0]["id"], "tag1")
        self.assertEqual(invoke_operation(self.client, "get_dataset", {"dataset_id": "kb"})["result"]["retrieval_model_dict"], self.saved)

    def test_multi_deduplicates_sources_interleaves_and_reports_partial_failures(self):
        def retrieve(dataset, payload):
            if dataset == "bad":
                raise RuntimeError("forbidden")
            return {"query": {"content": "q"}, "records": [{"segment": {"id": "s1", "document_id": "doc", "content": "Shared"}, "score": 0.8}, {"segment": {"id": "s2", "content": dataset}, "score": 0.7}]}
        self.client.retrieve_chunks.side_effect = retrieve
        result = retrieve_multiple(self.client, {"dataset_ids": "a,b,a,bad", "query": "q", "max_results": 2})
        self.assertEqual(result["dataset_ids"], ["a", "b", "bad"])
        self.assertEqual(result["total_count"], 3)
        self.assertTrue(result["has_more"])
        self.assertTrue(result["partial_failure"])
        self.assertEqual(result["result"][1]["content"], "a")
        self.assertEqual(len(result["result"][0]["sources"]), 2)
        self.assertEqual(result["errors"][0]["dataset_id"], "bad")
        self.assertEqual(self.client.retrieve_chunks.call_count, 3)

    def test_multi_all_failed_and_empty_success_are_distinct(self):
        self.client.retrieve_chunks.side_effect = RuntimeError("failed")
        with self.assertRaisesRegex(ValueError, "All knowledge base retrievals failed"):
            retrieve_multiple(self.client, {"dataset_ids": "a,b", "query": "q"})
        self.client.retrieve_chunks.side_effect = None
        self.client.retrieve_chunks.return_value = {"records": []}
        result = retrieve_multiple(self.client, {"dataset_ids": "a,b", "query": "q"})
        self.assertEqual(result["count"], 0)
        self.assertFalse(result["partial_failure"])

    def test_multi_keeps_different_questions_with_the_same_answer(self):
        self.client.retrieve_chunks.side_effect = lambda dataset, payload: {"records": [{"segment": {"id": "s1", "content": dataset, "answer": "Yes"}}]}
        result = retrieve_multiple(self.client, {"dataset_ids": "question-a,question-b", "query": "q"})
        self.assertEqual(result["count"], 2)
        self.assertEqual([item["question"] for item in result["result"]], ["question-a", "question-b"])

    def test_external_threshold_explicitly_disabled(self):
        self.client.get_dataset.return_value = {"provider": "external", "external_retrieval_model": {"top_k": 3}}
        payload = retrieve_payload(self.client, "kb", {"query": "q", "score_threshold": 0.8, "score_threshold_enabled": False})
        self.assertFalse(payload["external_retrieval_model"]["score_threshold_enabled"])

    def test_switching_to_weighted_reranking_removes_saved_model(self):
        model = retrieve_payload(self.client, "kb", {"query": "q", "reranking_mode": "weighted_score"})["retrieval_model"]
        self.assertNotIn("reranking_model", model)

    @patch("provider.dify_knowledge_api.requests.request")
    def test_new_api_routes_and_bodies(self, request):
        request.return_value.status_code = 200
        request.return_value.json.return_value = {}
        client = DifyKnowledgeClient("https://example.com", "test-key")
        for method, path, action in [
            ("GET", "/datasets/kb", lambda: client.get_dataset("kb")),
            ("GET", "/datasets/kb/metadata", lambda: client.list_metadata_fields("kb")),
            ("GET", "/datasets/tags", client.list_tags),
            ("GET", "/datasets/kb/documents/batch/indexing-status", lambda: client.get_indexing_status("kb", "batch")),
            ("POST", "/datasets/kb/document/create-by-text", lambda: client.create_document_by_text("kb", {"name": "FAQ", "text": "Text"})),
            ("POST", "/datasets/kb/documents/doc/update-by-text", lambda: client.update_document_by_text("kb", "doc", {"text": "Text"})),
        ]:
            action()
            self.assertEqual(request.call_args.kwargs["method"], method)
            self.assertEqual(request.call_args.kwargs["url"], "https://example.com/v1" + path)
            if method == "POST":
                self.assertEqual(request.call_args.kwargs["json"]["text"], "Text")


if __name__ == "__main__":
    unittest.main()
