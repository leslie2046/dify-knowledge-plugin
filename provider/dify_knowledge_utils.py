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

EXTERNAL_RETRIEVAL_OVERRIDE_FIELDS = {
    "top_k",
    "score_threshold_enabled",
    "score_threshold",
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


def build_retrieve_payload(tool_parameters: Mapping[str, Any], dataset_details: Mapping[str, Any]) -> dict[str, Any]:
    query = str(tool_parameters.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")

    payload: dict[str, Any] = {"query": query}
    attachment_ids = parse_string_list(tool_parameters.get("attachment_ids"))
    if attachment_ids:
        payload["attachment_ids"] = attachment_ids

    provider = str(dataset_details.get("provider") or "vendor")

    if provider == "external":
        if has_requested_overrides(tool_parameters, INTERNAL_ONLY_OVERRIDE_FIELDS):
            raise ValueError(
                "search_method, reranking, and hybrid weight overrides are only supported for internal knowledge bases"
            )
        if has_requested_overrides(tool_parameters, EXTERNAL_RETRIEVAL_OVERRIDE_FIELDS):
            payload["external_retrieval_model"] = build_external_retrieval_model(
                tool_parameters=tool_parameters,
                dataset_details=dataset_details,
            )
    elif has_requested_overrides(tool_parameters, INTERNAL_RETRIEVAL_OVERRIDE_FIELDS):
        payload["retrieval_model"] = build_internal_retrieval_model(
            tool_parameters=tool_parameters,
            dataset_details=dataset_details,
        )

    return payload


def build_internal_retrieval_model(
    tool_parameters: Mapping[str, Any], dataset_details: Mapping[str, Any]
) -> dict[str, Any]:
    base_config = dict(dataset_details.get("retrieval_model_dict") or {})
    model = {
        "search_method": str(base_config.get("search_method") or "semantic_search"),
        "reranking_enable": _coerce_bool(base_config.get("reranking_enable"), default=False),
        "top_k": _coerce_int(base_config.get("top_k"), default=3),
        "score_threshold_enabled": _coerce_bool(base_config.get("score_threshold_enabled"), default=False),
    }

    reranking_mode = base_config.get("reranking_mode")
    if reranking_mode is not None:
        model["reranking_mode"] = reranking_mode

    reranking_model = _copy_mapping(base_config.get("reranking_model"))
    if reranking_model:
        model["reranking_model"] = reranking_model

    weights = _copy_mapping(base_config.get("weights"))
    if weights:
        model["weights"] = weights

    metadata_filtering_conditions = _copy_mapping(base_config.get("metadata_filtering_conditions"))
    if metadata_filtering_conditions:
        model["metadata_filtering_conditions"] = metadata_filtering_conditions

    if base_config.get("score_threshold") is not None:
        model["score_threshold"] = _coerce_float(base_config.get("score_threshold"), default=0.0)

    if _has_non_empty_value(tool_parameters.get("search_method")):
        model["search_method"] = str(tool_parameters.get("search_method")).strip()

    if _has_non_empty_value(tool_parameters.get("top_k")):
        model["top_k"] = _coerce_int(tool_parameters.get("top_k"), default=model["top_k"])

    score_threshold_provided = "score_threshold" in tool_parameters and tool_parameters.get("score_threshold") is not None
    score_threshold_enabled_provided = (
        "score_threshold_enabled" in tool_parameters and tool_parameters.get("score_threshold_enabled") is not None
    )
    if score_threshold_enabled_provided:
        model["score_threshold_enabled"] = _coerce_bool(
            tool_parameters.get("score_threshold_enabled"),
            default=model["score_threshold_enabled"],
        )
    elif score_threshold_provided:
        model["score_threshold_enabled"] = True

    if score_threshold_provided:
        model["score_threshold"] = _coerce_float(tool_parameters.get("score_threshold"), default=0.0)
    elif not model["score_threshold_enabled"]:
        model.pop("score_threshold", None)

    reranking_mode_value = _clean_string(tool_parameters.get("reranking_mode"))
    reranking_provider_name = _clean_string(tool_parameters.get("reranking_provider_name"))
    reranking_model_name = _clean_string(tool_parameters.get("reranking_model_name"))
    reranking_model_fields_provided = bool(reranking_provider_name or reranking_model_name)
    reranking_enable_provided = "reranking_enable" in tool_parameters and tool_parameters.get("reranking_enable") is not None
    if reranking_enable_provided:
        model["reranking_enable"] = _coerce_bool(
            tool_parameters.get("reranking_enable"),
            default=model["reranking_enable"],
        )
    elif reranking_mode_value or reranking_model_fields_provided:
        model["reranking_enable"] = True

    if model["reranking_enable"]:
        resolved_reranking_mode = (
            reranking_mode_value
            or model.get("reranking_mode")
            or ("reranking_model" if reranking_model_fields_provided else "weighted_score")
        )
        model["reranking_mode"] = resolved_reranking_mode
        if resolved_reranking_mode == "reranking_model":
            current_reranking_model = _copy_mapping(model.get("reranking_model"))
            provider_name = reranking_provider_name or _clean_string(
                current_reranking_model.get("reranking_provider_name") if current_reranking_model else None
            )
            model_name = reranking_model_name or _clean_string(
                current_reranking_model.get("reranking_model_name") if current_reranking_model else None
            )
            if not provider_name or not model_name:
                raise ValueError(
                    "reranking_provider_name and reranking_model_name are required when reranking_mode is reranking_model"
                )
            model["reranking_model"] = {
                "reranking_provider_name": provider_name,
                "reranking_model_name": model_name,
            }
        else:
            model.pop("reranking_model", None)
    else:
        model["reranking_mode"] = None
        model.pop("reranking_model", None)

    weight_type = _clean_string(tool_parameters.get("weight_type"))
    vector_weight_provided = "vector_weight" in tool_parameters and tool_parameters.get("vector_weight") is not None
    keyword_weight_provided = "keyword_weight" in tool_parameters and tool_parameters.get("keyword_weight") is not None
    if weight_type or vector_weight_provided or keyword_weight_provided:
        if model["search_method"] != "hybrid_search":
            raise ValueError("weight_type, vector_weight, and keyword_weight require search_method=hybrid_search")

        weights_value = _copy_mapping(model.get("weights"))
        if not weights_value:
            weights_value = {}

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


def build_external_retrieval_model(
    tool_parameters: Mapping[str, Any], dataset_details: Mapping[str, Any]
) -> dict[str, Any]:
    base_config = dict(dataset_details.get("external_retrieval_model") or {})
    model = {
        "top_k": _coerce_int(base_config.get("top_k"), default=3),
        "score_threshold_enabled": _coerce_bool(base_config.get("score_threshold_enabled"), default=False),
    }

    if base_config.get("score_threshold") is not None:
        model["score_threshold"] = _coerce_float(base_config.get("score_threshold"), default=0.0)

    if _has_non_empty_value(tool_parameters.get("top_k")):
        model["top_k"] = _coerce_int(tool_parameters.get("top_k"), default=model["top_k"])

    score_threshold_provided = "score_threshold" in tool_parameters and tool_parameters.get("score_threshold") is not None
    score_threshold_enabled_provided = (
        "score_threshold_enabled" in tool_parameters and tool_parameters.get("score_threshold_enabled") is not None
    )
    if score_threshold_enabled_provided:
        model["score_threshold_enabled"] = _coerce_bool(
            tool_parameters.get("score_threshold_enabled"),
            default=model["score_threshold_enabled"],
        )
    elif score_threshold_provided:
        model["score_threshold_enabled"] = True

    if score_threshold_provided:
        model["score_threshold"] = _coerce_float(tool_parameters.get("score_threshold"), default=0.0)
    elif not model["score_threshold_enabled"]:
        model.pop("score_threshold", None)

    return model


def normalize_retrieval_response(response_data: Mapping[str, Any], dataset_id: str) -> dict[str, Any]:
    normalized_records: list[dict[str, Any]] = []

    for record in response_data.get("records", []) or []:
        segment = record.get("segment") or {}
        document = segment.get("document") or {}
        content = _clean_string(segment.get("answer")) or _clean_string(segment.get("content"))
        normalized_records.append(
            {
                "segment_id": segment.get("id"),
                "document_id": segment.get("document_id") or document.get("id"),
                "document_name": document.get("name"),
                "title": document.get("name") or f"Chunk {segment.get('position') or ''}".strip(),
                "content": content,
                "answer": _clean_string(segment.get("answer")),
                "score": record.get("score"),
                "summary": record.get("summary"),
                "keywords": list(segment.get("keywords") or []),
                "metadata": {
                    "segment_position": segment.get("position"),
                    "word_count": segment.get("word_count"),
                    "tokens": segment.get("tokens"),
                    "data_source_type": document.get("data_source_type"),
                    "doc_type": document.get("doc_type"),
                    "doc_metadata": document.get("doc_metadata"),
                    "files": record.get("files") or [],
                    "child_chunks": record.get("child_chunks") or [],
                },
            }
        )

    return {
        "query": ((response_data.get("query") or {}).get("content") or ""),
        "dataset_id": dataset_id,
        "count": len(normalized_records),
        "result": normalized_records,
    }


def normalize_dataset_list_response(response_data: Mapping[str, Any]) -> dict[str, Any]:
    normalized_datasets: list[dict[str, Any]] = []

    for dataset in response_data.get("data", []) or []:
        normalized_datasets.append(
            {
                "id": dataset.get("id"),
                "name": dataset.get("name"),
                "description": dataset.get("description"),
                "provider": dataset.get("provider"),
                "permission": dataset.get("permission"),
                "indexing_technique": dataset.get("indexing_technique"),
                "document_count": dataset.get("document_count"),
                "total_documents": dataset.get("total_documents"),
                "total_available_documents": dataset.get("total_available_documents"),
                "word_count": dataset.get("word_count"),
                "embedding_model": dataset.get("embedding_model"),
                "embedding_model_provider": dataset.get("embedding_model_provider"),
                "enable_api": dataset.get("enable_api"),
                "is_published": dataset.get("is_published"),
                "is_multimodal": dataset.get("is_multimodal"),
                "tags": list(dataset.get("tags") or []),
                "retrieval_model": _copy_mapping(dataset.get("retrieval_model_dict")),
                "external_retrieval_model": _copy_mapping(dataset.get("external_retrieval_model")),
            }
        )

    return {
        "page": response_data.get("page"),
        "limit": response_data.get("limit"),
        "total": response_data.get("total"),
        "has_more": response_data.get("has_more"),
        "count": len(normalized_datasets),
        "result": normalized_datasets,
    }


def normalize_document_list_response(response_data: Mapping[str, Any], dataset_id: str) -> dict[str, Any]:
    normalized_documents: list[dict[str, Any]] = []

    for document in response_data.get("data", []) or []:
        normalized_documents.append(
            {
                "id": document.get("id"),
                "dataset_id": dataset_id,
                "name": document.get("name"),
                "position": document.get("position"),
                "data_source_type": document.get("data_source_type"),
                "data_source_info": _copy_mapping(document.get("data_source_info")),
                "data_source_detail": _copy_mapping(document.get("data_source_detail_dict")),
                "created_from": document.get("created_from"),
                "created_by": document.get("created_by"),
                "created_at": document.get("created_at"),
                "tokens": document.get("tokens"),
                "word_count": document.get("word_count"),
                "hit_count": document.get("hit_count"),
                "indexing_status": document.get("indexing_status"),
                "display_status": document.get("display_status"),
                "enabled": document.get("enabled"),
                "archived": document.get("archived"),
                "error": document.get("error"),
                "doc_form": document.get("doc_form"),
                "doc_metadata": document.get("doc_metadata") or [],
                "need_summary": document.get("need_summary"),
                "summary_index_status": document.get("summary_index_status"),
            }
        )

    return {
        "dataset_id": dataset_id,
        "page": response_data.get("page"),
        "limit": response_data.get("limit"),
        "total": response_data.get("total"),
        "has_more": response_data.get("has_more"),
        "count": len(normalized_documents),
        "result": normalized_documents,
    }


def has_requested_overrides(tool_parameters: Mapping[str, Any], keys: set[str]) -> bool:
    return any(key in tool_parameters and _has_non_empty_value(tool_parameters.get(key)) for key in keys)


def _clean_string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _copy_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items()}


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
