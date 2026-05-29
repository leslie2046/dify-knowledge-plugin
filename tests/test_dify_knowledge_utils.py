import unittest

from provider.dify_knowledge_utils import (
    build_list_documents_params,
    build_list_datasets_params,
    build_retrieve_payload,
    normalize_base_url,
    normalize_dataset_list_response,
    normalize_document_list_response,
    normalize_retrieval_response,
    parse_string_list,
    select_dataset_id,
)


class DifyKnowledgeUtilsTestCase(unittest.TestCase):
    def test_normalize_base_url_adds_v1(self) -> None:
        self.assertEqual(normalize_base_url("https://api.dify.ai"), "https://api.dify.ai/v1")
        self.assertEqual(normalize_base_url("https://api.dify.ai/v1/"), "https://api.dify.ai/v1")

    def test_parse_string_list_supports_csv_and_json_array(self) -> None:
        self.assertEqual(parse_string_list("a,b, c "), ["a", "b", "c"])
        self.assertEqual(parse_string_list('["a", "b"]'), ["a", "b"])

    def test_select_dataset_id_requires_parameter(self) -> None:
        with self.assertRaises(ValueError):
            select_dataset_id(tool_parameters={})

    def test_build_list_datasets_params_supports_filters(self) -> None:
        params = build_list_datasets_params(
            {
                "page": "2",
                "limit": "10",
                "keyword": "product",
                "include_all": "true",
                "tag_ids": '["tag-1", "tag-2"]',
            }
        )
        self.assertEqual(params["page"], 2)
        self.assertEqual(params["limit"], 10)
        self.assertEqual(params["keyword"], "product")
        self.assertTrue(params["include_all"])
        self.assertEqual(params["tag_ids"], ["tag-1", "tag-2"])

    def test_build_list_documents_params_supports_filters(self) -> None:
        params = build_list_documents_params(
            {
                "page": "3",
                "limit": "15",
                "keyword": "guide",
                "status": "available",
            }
        )
        self.assertEqual(params["page"], 3)
        self.assertEqual(params["limit"], 15)
        self.assertEqual(params["keyword"], "guide")
        self.assertEqual(params["status"], "available")

    def test_internal_payload_preserves_dataset_defaults(self) -> None:
        dataset_details = {
            "provider": "vendor",
            "retrieval_model_dict": {
                "search_method": "hybrid_search",
                "reranking_enable": True,
                "reranking_mode": "reranking_model",
                "reranking_model": {
                    "reranking_provider_name": "cohere",
                    "reranking_model_name": "rerank-v3.5",
                },
                "weights": {
                    "weight_type": "customized",
                    "vector_setting": {"vector_weight": 0.7},
                    "keyword_setting": {"keyword_weight": 0.3},
                },
                "top_k": 5,
                "score_threshold_enabled": False,
                "score_threshold": None,
            },
        }
        payload = build_retrieve_payload({"query": "dify", "top_k": 8}, dataset_details)
        self.assertEqual(payload["query"], "dify")
        self.assertEqual(payload["retrieval_model"]["search_method"], "hybrid_search")
        self.assertTrue(payload["retrieval_model"]["reranking_enable"])
        self.assertEqual(payload["retrieval_model"]["top_k"], 8)

    def test_external_payload_rejects_internal_only_overrides(self) -> None:
        dataset_details = {
            "provider": "external",
            "external_retrieval_model": {
                "top_k": 3,
                "score_threshold_enabled": False,
                "score_threshold": None,
            },
        }
        with self.assertRaises(ValueError):
            build_retrieve_payload(
                {
                    "query": "dify",
                    "search_method": "semantic_search",
                },
                dataset_details,
            )

    def test_normalize_retrieval_response_maps_records(self) -> None:
        response = {
            "query": {"content": "What is Dify?"},
            "records": [
                {
                    "segment": {
                        "id": "seg-1",
                        "position": 1,
                        "document_id": "doc-1",
                        "content": "Dify is an open-source LLM app platform.",
                        "answer": "",
                        "word_count": 7,
                        "tokens": 10,
                        "keywords": ["dify", "platform"],
                        "document": {
                            "id": "doc-1",
                            "name": "guide.txt",
                            "data_source_type": "upload_file",
                            "doc_type": None,
                            "doc_metadata": {"lang": "en"},
                        },
                    },
                    "score": 0.92,
                    "child_chunks": [],
                    "files": [],
                    "summary": None,
                }
            ],
        }
        normalized = normalize_retrieval_response(response, "kb-1")
        self.assertEqual(normalized["query"], "What is Dify?")
        self.assertEqual(normalized["dataset_id"], "kb-1")
        self.assertEqual(normalized["count"], 1)
        self.assertEqual(normalized["result"][0]["title"], "guide.txt")

    def test_normalize_dataset_list_response_maps_records(self) -> None:
        response = {
            "data": [
                {
                    "id": "kb-1",
                    "name": "Product Docs",
                    "description": "Technical documentation",
                    "provider": "vendor",
                    "permission": "only_me",
                    "indexing_technique": "high_quality",
                    "document_count": 3,
                    "total_documents": 3,
                    "total_available_documents": 3,
                    "word_count": 1200,
                    "embedding_model": "text-embedding-3-small",
                    "embedding_model_provider": "openai",
                    "enable_api": True,
                    "is_published": False,
                    "is_multimodal": False,
                    "tags": [{"id": "tag-1", "name": "product"}],
                    "retrieval_model_dict": {"search_method": "semantic_search"},
                    "external_retrieval_model": None,
                }
            ],
            "has_more": False,
            "limit": 20,
            "total": 1,
            "page": 1,
        }
        normalized = normalize_dataset_list_response(response)
        self.assertEqual(normalized["page"], 1)
        self.assertEqual(normalized["count"], 1)
        self.assertEqual(normalized["result"][0]["id"], "kb-1")
        self.assertEqual(normalized["result"][0]["name"], "Product Docs")
        self.assertEqual(normalized["result"][0]["retrieval_model"]["search_method"], "semantic_search")

    def test_normalize_document_list_response_maps_records(self) -> None:
        response = {
            "data": [
                {
                    "id": "doc-1",
                    "position": 1,
                    "data_source_type": "upload_file",
                    "data_source_info": {"upload_file_id": "file-1"},
                    "data_source_detail_dict": {
                        "upload_file": {
                            "id": "file-1",
                            "name": "guide.txt",
                            "size": 2048,
                        }
                    },
                    "name": "guide.txt",
                    "created_from": "api",
                    "created_by": "user-1",
                    "created_at": 1741267200,
                    "tokens": 512,
                    "indexing_status": "completed",
                    "error": None,
                    "enabled": True,
                    "archived": False,
                    "display_status": "available",
                    "word_count": 350,
                    "hit_count": 0,
                    "doc_form": "text_model",
                    "doc_metadata": [],
                    "summary_index_status": None,
                    "need_summary": False,
                }
            ],
            "has_more": False,
            "limit": 20,
            "total": 1,
            "page": 1,
        }
        normalized = normalize_document_list_response(response, "kb-1")
        self.assertEqual(normalized["dataset_id"], "kb-1")
        self.assertEqual(normalized["count"], 1)
        self.assertEqual(normalized["result"][0]["id"], "doc-1")
        self.assertEqual(normalized["result"][0]["display_status"], "available")
        self.assertEqual(normalized["result"][0]["data_source_detail"]["upload_file"]["name"], "guide.txt")


if __name__ == "__main__":
    unittest.main()
