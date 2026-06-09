from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse, urlunparse

INTERNAL_ONLY_OVERRIDE_FIELDS = {
    "search_method",
    "reranking_enable",
    "reranking_mode",
    "reranking_provider_name",
    "reranking_model_name",
    "weight_type",
    "vector_weight",
    "keyword_weight",
}

INTERNAL_RETRIEVAL_OVERRIDE_FIELDS = INTERNAL_ONLY_OVERRIDE_FIELDS | {
    "top_k",
    "score_threshold_enabled",
    "score_threshold",
}

SUPPORTED_MODEL_TYPES = {
    "text-embedding",
    "rerank",
    "llm",
    "tts",
    "speech2text",
    "moderation",
}

MODEL_TYPE_ALIASES = {
    "embedding": "text-embedding",
    "text_embedding": "text-embedding",
    "textembedding": "text-embedding",
    "speech-to-text": "speech2text",
    "speech_to_text": "speech2text",
}


def normalize_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if not value:
        raise ValueError("base_url is required")

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("base_url must be a valid absolute URL")

    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        normalized_path = path
    elif not path:
        normalized_path = "/v1"
    else:
        normalized_path = f"{path}/v1"

    return urlunparse((parsed.scheme, parsed.netloc, normalized_path, "", "", ""))


def parse_string_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return [item for item in (str(entry).strip() for entry in value) if item]

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []

        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, list):
                return [item for item in (str(entry).strip() for entry in parsed) if item]

        return [item.strip() for item in text.split(",") if item.strip()]

    text = str(value).strip()
    return [text] if text else []


def select_dataset_id(tool_parameters: Mapping[str, Any]) -> str:
    dataset_id = str(tool_parameters.get("dataset_id") or "").strip()
    if dataset_id:
        return dataset_id

    raise ValueError("dataset_id is required")


def build_list_datasets_params(tool_parameters: Mapping[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "page": _coerce_int(tool_parameters.get("page"), default=1),
        "limit": _coerce_int(tool_parameters.get("limit"), default=20),
    }

    keyword = _clean_string(tool_parameters.get("keyword"))
    if keyword:
        params["keyword"] = keyword

    if "include_all" in tool_parameters and tool_parameters.get("include_all") is not None:
        params["include_all"] = _coerce_bool(tool_parameters.get("include_all"), default=False)

    tag_ids = parse_string_list(tool_parameters.get("tag_ids"))
    if tag_ids:
        params["tag_ids"] = tag_ids

    return params


def build_list_documents_params(tool_parameters: Mapping[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {
        "page": _coerce_int(tool_parameters.get("page"), default=1),
        "limit": _coerce_int(tool_parameters.get("limit"), default=20),
    }

    keyword = _clean_string(tool_parameters.get("keyword"))
    if keyword:
        params["keyword"] = keyword

    status = _clean_string(tool_parameters.get("status"))
    if status:
        params["status"] = status

    return params


def build_list_available_models_params(tool_parameters: Mapping[str, Any]) -> dict[str, str]:
    return {"model_type": select_model_type(tool_parameters)}


def build_retrieve_payload(tool_parameters: Mapping[str, Any]) -> dict[str, Any]:
    query = str(tool_parameters.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")

    payload: dict[str, Any] = {"query": query}
    attachment_ids = parse_string_list(tool_parameters.get("attachment_ids"))
    if attachment_ids:
        payload["attachment_ids"] = attachment_ids

    if has_requested_overrides(tool_parameters, INTERNAL_RETRIEVAL_OVERRIDE_FIELDS):
        payload["retrieval_model"] = build_internal_retrieval_model(tool_parameters=tool_parameters)

    return payload


def build_internal_retrieval_model(tool_parameters: Mapping[str, Any]) -> dict[str, Any]:
    reranking_mode_value = _clean_string(tool_parameters.get("reranking_mode"))
    reranking_provider_name = _clean_string(tool_parameters.get("reranking_provider_name"))
    reranking_model_name = _clean_string(tool_parameters.get("reranking_model_name"))
    reranking_model_fields_provided = bool(reranking_provider_name or reranking_model_name)
    reranking_enable_provided = "reranking_enable" in tool_parameters and tool_parameters.get("reranking_enable") is not None
    reranking_requested = reranking_enable_provided or bool(reranking_mode_value or reranking_model_fields_provided)
    weight_type = _clean_string(tool_parameters.get("weight_type"))
    vector_weight_provided = "vector_weight" in tool_parameters and tool_parameters.get("vector_weight") is not None
    keyword_weight_provided = "keyword_weight" in tool_parameters and tool_parameters.get("keyword_weight") is not None
    weights_requested = bool(weight_type or vector_weight_provided or keyword_weight_provided)
    default_search_method = "hybrid_search" if reranking_requested or weights_requested else "semantic_search"

    model = {
        "search_method": default_search_method,
        "reranking_enable": _coerce_bool(tool_parameters.get("reranking_enable"), default=bool(reranking_mode_value or reranking_model_fields_provided)),
        "top_k": _coerce_int(tool_parameters.get("top_k"), default=3),
        "score_threshold_enabled": _coerce_bool(
            tool_parameters.get("score_threshold_enabled"),
            default=("score_threshold" in tool_parameters and tool_parameters.get("score_threshold") is not None),
        ),
    }

    if _has_non_empty_value(tool_parameters.get("search_method")):
        model["search_method"] = str(tool_parameters.get("search_method")).strip()

    score_threshold_provided = "score_threshold" in tool_parameters and tool_parameters.get("score_threshold") is not None
    if score_threshold_provided:
        model["score_threshold_enabled"] = True

    if score_threshold_provided:
        model["score_threshold"] = _coerce_float(tool_parameters.get("score_threshold"), default=0.0)
    elif not model["score_threshold_enabled"]:
        model.pop("score_threshold", None)

    if model["reranking_enable"]:
        resolved_reranking_mode = (
            reranking_mode_value
            or ("reranking_model" if reranking_model_fields_provided else "weighted_score")
        )
        model["reranking_mode"] = resolved_reranking_mode
        if resolved_reranking_mode == "reranking_model":
            if not reranking_provider_name or not reranking_model_name:
                raise ValueError(
                    "reranking_provider_name and reranking_model_name are required when reranking_mode is reranking_model"
                )
            model["reranking_model"] = {
                "reranking_provider_name": reranking_provider_name,
                "reranking_model_name": reranking_model_name,
            }
        else:
            model.pop("reranking_model", None)
    else:
        model.pop("reranking_model", None)
        model.pop("reranking_mode", None)

    if weight_type or vector_weight_provided or keyword_weight_provided:
        if model["search_method"] != "hybrid_search":
            raise ValueError("weight_type, vector_weight, and keyword_weight require search_method=hybrid_search")

        weights_value: dict[str, Any] = {}

        if weight_type:
            weights_value["weight_type"] = weight_type
        elif vector_weight_provided or keyword_weight_provided:
            weights_value["weight_type"] = "customized"

        if vector_weight_provided:
            vector_setting = dict(weights_value.get("vector_setting") or {})
            vector_setting["vector_weight"] = _coerce_float(tool_parameters.get("vector_weight"), default=0.0)
            weights_value["vector_setting"] = vector_setting

        if keyword_weight_provided:
            keyword_setting = dict(weights_value.get("keyword_setting") or {})
            keyword_setting["keyword_weight"] = _coerce_float(tool_parameters.get("keyword_weight"), default=0.0)
            weights_value["keyword_setting"] = keyword_setting

        model["weights"] = weights_value
    elif model["search_method"] != "hybrid_search":
        model.pop("weights", None)

    return model


def normalize_retrieval_response(response_data: Any, dataset_id: str) -> dict[str, Any]:
    response_mapping = _as_mapping(response_data)
    normalized_records: list[dict[str, Any]] = []

    for record in _as_list(response_mapping.get("records")):
        record_mapping = _as_mapping(record)
        segment = _as_mapping(record_mapping.get("segment"))
        document = _as_mapping(segment.get("document"))
        content = _clean_string(segment.get("answer")) or _clean_string(segment.get("content")) or _clean_string(record)
        normalized_records.append(
            {
                "segment_id": segment.get("id"),
                "document_id": segment.get("document_id") or document.get("id"),
                "document_name": document.get("name"),
                "title": document.get("name") or f"Chunk {segment.get('position') or ''}".strip(),
                "content": content,
                "answer": _clean_string(segment.get("answer")),
                "score": record_mapping.get("score"),
                "summary": record_mapping.get("summary"),
                "keywords": _as_list(segment.get("keywords")),
                "metadata": {
                    "segment_position": segment.get("position"),
                    "word_count": segment.get("word_count"),
                    "tokens": segment.get("tokens"),
                    "data_source_type": document.get("data_source_type"),
                    "doc_type": document.get("doc_type"),
                    "doc_metadata": document.get("doc_metadata"),
                    "files": _as_list(record_mapping.get("files")),
                    "child_chunks": _as_list(record_mapping.get("child_chunks")),
                },
            }
        )

    return {
        "query": _extract_query_content(response_mapping.get("query")),
        "dataset_id": dataset_id,
        "count": len(normalized_records),
        "result": normalized_records,
    }


def normalize_dataset_list_response(response_data: Any) -> dict[str, Any]:
    response_mapping = _as_mapping(response_data)
    normalized_datasets: list[dict[str, Any]] = []

    for dataset in _as_list(response_mapping.get("data")):
        dataset_mapping = _as_mapping(dataset)
        normalized_datasets.append(
            {
                "id": dataset_mapping.get("id"),
                "name": dataset_mapping.get("name"),
                "description": dataset_mapping.get("description"),
                "provider": dataset_mapping.get("provider"),
                "permission": dataset_mapping.get("permission"),
                "indexing_technique": dataset_mapping.get("indexing_technique"),
                "document_count": dataset_mapping.get("document_count"),
                "total_documents": dataset_mapping.get("total_documents"),
                "total_available_documents": dataset_mapping.get("total_available_documents"),
                "word_count": dataset_mapping.get("word_count"),
                "embedding_model": dataset_mapping.get("embedding_model"),
                "embedding_model_provider": dataset_mapping.get("embedding_model_provider"),
                "enable_api": dataset_mapping.get("enable_api"),
                "is_published": dataset_mapping.get("is_published"),
                "is_multimodal": dataset_mapping.get("is_multimodal"),
                "tags": _as_list(dataset_mapping.get("tags")),
                "retrieval_model": _copy_mapping(dataset_mapping.get("retrieval_model_dict")),
                "external_retrieval_model": _copy_mapping(dataset_mapping.get("external_retrieval_model")),
            }
        )

    return {
        "page": response_mapping.get("page"),
        "limit": response_mapping.get("limit"),
        "total": response_mapping.get("total"),
        "has_more": response_mapping.get("has_more"),
        "count": len(normalized_datasets),
        "result": normalized_datasets,
    }


def normalize_document_list_response(response_data: Any, dataset_id: str) -> dict[str, Any]:
    response_mapping = _as_mapping(response_data)
    normalized_documents: list[dict[str, Any]] = []

    for document in _as_list(response_mapping.get("data")):
        document_mapping = _as_mapping(document)
        normalized_documents.append(
            {
                "id": document_mapping.get("id"),
                "dataset_id": dataset_id,
                "name": document_mapping.get("name"),
                "position": document_mapping.get("position"),
                "data_source_type": document_mapping.get("data_source_type"),
                "data_source_info": _copy_mapping(document_mapping.get("data_source_info")),
                "data_source_detail": _copy_mapping(document_mapping.get("data_source_detail_dict")),
                "created_from": document_mapping.get("created_from"),
                "created_by": document_mapping.get("created_by"),
                "created_at": document_mapping.get("created_at"),
                "tokens": document_mapping.get("tokens"),
                "word_count": document_mapping.get("word_count"),
                "hit_count": document_mapping.get("hit_count"),
                "indexing_status": document_mapping.get("indexing_status"),
                "display_status": document_mapping.get("display_status"),
                "enabled": document_mapping.get("enabled"),
                "archived": document_mapping.get("archived"),
                "error": document_mapping.get("error"),
                "doc_form": document_mapping.get("doc_form"),
                "doc_metadata": _as_list(document_mapping.get("doc_metadata")),
                "need_summary": document_mapping.get("need_summary"),
                "summary_index_status": document_mapping.get("summary_index_status"),
            }
        )

    return {
        "dataset_id": dataset_id,
        "page": response_mapping.get("page"),
        "limit": response_mapping.get("limit"),
        "total": response_mapping.get("total"),
        "has_more": response_mapping.get("has_more"),
        "count": len(normalized_documents),
        "result": normalized_documents,
    }


def normalize_available_models_response(response_data: Any, model_type: str) -> dict[str, Any]:
    response_mapping = _as_mapping(response_data)
    normalized_providers: list[dict[str, Any]] = []
    model_count = 0

    for provider in _as_list(response_mapping.get("data")):
        provider_mapping = _as_mapping(provider)
        normalized_models: list[dict[str, Any]] = []

        for model in _as_list(provider_mapping.get("models")):
            model_mapping = _as_mapping(model)
            normalized_models.append(
                {
                    "model": model_mapping.get("model"),
                    "label": _copy_mapping(model_mapping.get("label")),
                    "model_type": model_mapping.get("model_type") or model_type,
                    "features": _as_list(model_mapping.get("features")),
                    "fetch_from": model_mapping.get("fetch_from"),
                    "model_properties": _copy_mapping(model_mapping.get("model_properties")),
                    "status": model_mapping.get("status"),
                }
            )

        model_count += len(normalized_models)
        normalized_providers.append(
            {
                "provider": provider_mapping.get("provider"),
                "label": _copy_mapping(provider_mapping.get("label")),
                "icon_small": _copy_mapping(provider_mapping.get("icon_small")),
                "icon_large": _copy_mapping(provider_mapping.get("icon_large")),
                "status": provider_mapping.get("status"),
                "model_count": len(normalized_models),
                "models": normalized_models,
            }
        )

    return {
        "model_type": model_type,
        "provider_count": len(normalized_providers),
        "model_count": model_count,
        "result": normalized_providers,
    }


def has_requested_overrides(tool_parameters: Mapping[str, Any], keys: set[str]) -> bool:
    return any(key in tool_parameters and _has_non_empty_value(tool_parameters.get(key)) for key in keys)


def select_model_type(tool_parameters: Mapping[str, Any]) -> str:
    raw_model_type = _clean_string(tool_parameters.get("model_type")).lower()
    if not raw_model_type:
        raise ValueError("model_type is required")

    model_type = MODEL_TYPE_ALIASES.get(raw_model_type, raw_model_type)
    if model_type not in SUPPORTED_MODEL_TYPES:
        allowed_values = ", ".join(sorted(SUPPORTED_MODEL_TYPES))
        raise ValueError(f"model_type must be one of: {allowed_values}")

    return model_type


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _extract_query_content(value: Any) -> str:
    if isinstance(value, Mapping):
        return _clean_string(value.get("content") or value.get("query") or value.get("text"))
    return _clean_string(value)


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off", ""}:
            return False

    raise ValueError(f"invalid boolean value: {value}")


def _coerce_int(value: Any, *, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _coerce_float(value: Any, *, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _has_non_empty_value(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)

    return True
