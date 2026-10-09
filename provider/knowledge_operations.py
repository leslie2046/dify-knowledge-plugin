from __future__ import annotations

import json
import math
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Any

from provider.dify_knowledge_utils import (
    INTERNAL_ONLY_OVERRIDE_FIELDS,
    INTERNAL_RETRIEVAL_OVERRIDE_FIELDS,
    build_internal_retrieval_model,
    build_retrieve_payload,
    has_requested_overrides,
    normalize_retrieval_response,
    parse_string_list,
)


def required_string(parameters: Mapping[str, Any], name: str) -> str:
    value = parameters.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    return value.strip()


def json_object(value: Any, name: str) -> dict[str, Any] | None:
    if value is None or value == "":
        return None
    try:
        result = json.loads(value) if isinstance(value, str) else value
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a JSON object") from exc
    if not isinstance(result, dict):
        raise ValueError(f"{name} must be a JSON object")
    return deepcopy(result)


def metadata_conditions(value: Any) -> dict[str, Any] | None:
    result = json_object(value, "metadata_filtering_conditions")
    if result is None:
        return None
    if result.get("logical_operator", "and") not in ("and", "or"):
        raise ValueError("metadata logical_operator must be and or or")
    conditions = result.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("metadata conditions must be a non-empty array")
    operators = {"contains", "not contains", "start with", "end with", "is", "is not", "empty", "not empty", "in", "not in", "=", "≠", ">", "<", "≥", "≤", "before", "after"}
    aliases = {"!=": "≠", ">=": "≥", "<=": "≤"}
    for condition in conditions:
        if not isinstance(condition, dict):
            raise ValueError("each metadata condition must be an object")
        required_string(condition, "name")
        operator = aliases.get(condition.get("comparison_operator"), condition.get("comparison_operator"))
        if operator not in operators:
            raise ValueError("unsupported metadata comparison_operator")
        condition["comparison_operator"] = operator
        if operator in ("empty", "not empty"):
            condition.pop("value", None)
        elif operator in ("in", "not in"):
            if not isinstance(condition.get("value"), list) or not all(isinstance(v, str) for v in condition["value"]):
                raise ValueError("in and not in require an array of strings")
        elif operator in ("=", "≠", ">", "<", "≥", "≤", "before", "after"):
            value = condition.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("numeric and time metadata operators require a finite number")
        elif not isinstance(condition.get("value"), str):
            raise ValueError("string metadata operators require a string value")
    return result


def _merge(base: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def retrieve_payload(client: Any, dataset_id: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    query = required_string(parameters, "query")
    if len(query) > 250:
        raise ValueError("query must be at most 250 characters")
    filters = metadata_conditions(parameters.get("metadata_filtering_conditions"))
    for key, minimum, maximum in (("top_k", 1, 50), ("score_threshold", 0, 1), ("vector_weight", 0, 1), ("keyword_weight", 0, 1)):
        if parameters.get(key) is not None and parameters.get(key) != "":
            value = float(parameters[key])
            if not math.isfinite(value) or not minimum <= value <= maximum or (key == "top_k" and int(value) != value):
                raise ValueError(f"{key} is outside its allowed range")
    overrides = has_requested_overrides(parameters, INTERNAL_RETRIEVAL_OVERRIDE_FIELDS)
    payload = build_retrieve_payload({"query": query, "attachment_ids": parameters.get("attachment_ids")})
    if not overrides and filters is None:
        return payload
    dataset = client.get_dataset(dataset_id)
    if dataset.get("provider") == "external":
        if filters is not None or has_requested_overrides(parameters, INTERNAL_ONLY_OVERRIDE_FIELDS):
            raise ValueError("metadata filters and internal retrieval overrides are unsupported for external knowledge bases")
        model = deepcopy(dataset.get("external_retrieval_model") or {})
        changes = build_internal_retrieval_model(parameters)
        for key in ("top_k", "score_threshold_enabled", "score_threshold"):
            if parameters.get(key) is not None and parameters.get(key) != "":
                model[key] = changes.get(key)
        if parameters.get("score_threshold_enabled") is not None and parameters.get("score_threshold_enabled") != "":
            model["score_threshold_enabled"] = str(parameters["score_threshold_enabled"]).lower() in ("true", "1")
        elif parameters.get("score_threshold") is not None and parameters.get("score_threshold") != "":
            model["score_threshold_enabled"] = True
        payload["external_retrieval_model"] = model
        return payload
    saved = dataset.get("retrieval_model_dict") or dataset.get("retrieval_model") or {}
    seed = {key: saved[key] for key in ("search_method", "reranking_enable", "reranking_mode", "top_k", "score_threshold_enabled", "score_threshold") if saved.get(key) is not None}
    seed.update(saved.get("reranking_model") or {})
    weights = saved.get("weights") or {}
    if weights.get("weight_type"):
        seed["weight_type"] = weights["weight_type"]
    for group, key in (("vector_setting", "vector_weight"), ("keyword_setting", "keyword_weight")):
        if (weights.get(group) or {}).get(key) is not None:
            seed[key] = weights[group][key]
    seed.update({key: parameters[key] for key in INTERNAL_RETRIEVAL_OVERRIDE_FIELDS if parameters.get(key) is not None and parameters.get(key) != ""})
    if seed.get("search_method") != "hybrid_search" and not has_requested_overrides(parameters, {"weight_type", "vector_weight", "keyword_weight"}):
        for key in ("weight_type", "vector_weight", "keyword_weight"):
            seed.pop(key, None)
    model = _merge(saved, build_internal_retrieval_model(seed))
    # An explicitly disabled threshold must win over a saved threshold value.
    if parameters.get("score_threshold_enabled") is not None and parameters.get("score_threshold_enabled") != "":
        model["score_threshold_enabled"] = str(parameters["score_threshold_enabled"]).lower() in ("true", "1")
    elif parameters.get("score_threshold") is None or parameters.get("score_threshold") == "":
        model["score_threshold_enabled"] = saved.get("score_threshold_enabled", False)
    if not model.get("reranking_enable"):
        model.pop("reranking_model", None)
        model.pop("reranking_mode", None)
    elif model.get("reranking_mode") != "reranking_model":
        model.pop("reranking_model", None)
    if model.get("search_method") != "hybrid_search":
        model.pop("weights", None)
    if filters is not None:
        model["metadata_filtering_conditions"] = filters
    payload["retrieval_model"] = model
    return payload


def document_payload(parameters: Mapping[str, Any], *, update: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for key in ("name", "text", "doc_form", "doc_language"):
        value = parameters.get(key)
        if value is not None and value != "":
            payload[key] = value
    if not update:
        payload["name"] = required_string(parameters, "name")
        required_string(parameters, "text")
        for key in ("indexing_technique", "embedding_model", "embedding_model_provider"):
            if parameters.get(key):
                payload[key] = parameters[key]
    elif "text" in payload:
        payload["name"] = required_string(parameters, "name")
        required_string(parameters, "text")
    elif "name" in payload:
        payload["name"] = required_string(parameters, "name")
    for key in ("process_rule", "retrieval_model"):
        parsed = json_object(parameters.get(key), key)
        if parsed is not None:
            payload[key] = parsed
    if not update and "process_rule" not in payload:
        payload["process_rule"] = {"mode": "automatic"}
    if not payload:
        raise ValueError("provide at least one document field to update")
    if payload.get("doc_form") not in (None, "text_model", "hierarchical_model", "qa_model"):
        raise ValueError("unsupported doc_form")
    if payload.get("indexing_technique") not in (None, "high_quality", "economy"):
        raise ValueError("unsupported indexing_technique")
    rule = payload.get("process_rule")
    if rule is not None and rule.get("mode") not in ("automatic", "custom", "hierarchical"):
        raise ValueError("process_rule.mode must be automatic, custom or hierarchical")
    if rule and rule["mode"] in ("custom", "hierarchical") and not isinstance(rule.get("rules"), dict):
        raise ValueError("custom and hierarchical process rules require a rules object")
    if payload.get("doc_form") == "hierarchical_model" and rule and rule["mode"] != "hierarchical":
        raise ValueError("hierarchical_model requires hierarchical process rules")
    return payload


def retrieve_multiple(client: Any, parameters: Mapping[str, Any]) -> dict[str, Any]:
    dataset_ids = list(dict.fromkeys(parse_string_list(parameters.get("dataset_ids"))))
    if not dataset_ids or len(dataset_ids) > 20:
        raise ValueError("dataset_ids must contain between 1 and 20 distinct IDs")
    required_string(parameters, "query")
    if len(parameters["query"].strip()) > 250:
        raise ValueError("query must be at most 250 characters")
    metadata_conditions(parameters.get("metadata_filtering_conditions"))
    raw_limit = parameters.get("max_results")
    numeric = float(20 if raw_limit is None or raw_limit == "" else raw_limit)
    if not math.isfinite(numeric) or not 1 <= numeric <= 200 or int(numeric) != numeric:
        raise ValueError("max_results must be an integer between 1 and 200")
    limit = int(numeric)

    def retrieve(dataset_id: str) -> dict[str, Any]:
        try:
            payload = retrieve_payload(client, dataset_id, parameters)
            raw_response = client.retrieve_chunks(dataset_id, payload)
            normalized = normalize_retrieval_response(raw_response, dataset_id)
            for item, record in zip(normalized["result"], raw_response.get("records", [])):
                segment = record.get("segment") if isinstance(record, dict) else None
                if item.get("answer") and isinstance(segment, dict):
                    item["question"] = segment.get("content")
            return normalized
        except Exception as exc:
            return {"dataset_id": dataset_id, "error": str(exc)}

    with ThreadPoolExecutor(max_workers=min(4, len(dataset_ids))) as pool:
        responses = list(pool.map(retrieve, dataset_ids))
    errors = [response for response in responses if "error" in response]
    successes = [response for response in responses if "error" not in response]
    if not successes:
        raise ValueError("All knowledge base retrievals failed: " + json.dumps(errors, ensure_ascii=False))
    records: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    # Interleave per-dataset ranks; scores from different datasets are not comparable.
    for rank in range(max((len(response["result"]) for response in successes), default=0)):
        for response in successes:
            if rank >= len(response["result"]):
                continue
            item = deepcopy(response["result"][rank])
            item["dataset_id"] = response["dataset_id"]
            source = {key: item.get(key) for key in ("dataset_id", "document_id", "document_name", "segment_id", "score")}
            key = json.dumps([item.get("content"), item.get("answer"), item.get("question")], ensure_ascii=False)
            if key in seen:
                seen[key]["sources"].append(source)
            else:
                item["sources"] = [source]
                seen[key] = item
                records.append(item)
    return {"query": parameters["query"].strip(), "dataset_ids": dataset_ids, "count": min(len(records), limit), "total_count": len(records), "has_more": len(records) > limit, "partial_failure": bool(errors), "errors": errors, "ordering": "round_robin_by_dataset_rank", "result": records[:limit]}


def invoke_operation(client: Any, operation: str, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if operation == "retrieve_multiple":
        return retrieve_multiple(client, parameters)
    if operation == "list_tags":
        response = client.list_tags()
        tags = response if isinstance(response, list) else response.get("data", [])
        return {"count": len(tags), "result": tags}
    dataset_id = required_string(parameters, "dataset_id")
    if operation == "get_dataset":
        result = client.get_dataset(dataset_id)
        return {"dataset_id": dataset_id, "result": result}
    if operation == "list_metadata_fields":
        response = client.list_metadata_fields(dataset_id)
        fields = response.get("doc_metadata") or []
        return {"dataset_id": dataset_id, "built_in_field_enabled": response.get("built_in_field_enabled", False), "count": len(fields), "result": fields}
    if operation in ("create_document_by_text", "update_document_by_text"):
        update = operation == "update_document_by_text"
        payload = document_payload(parameters, update=update)
        if update:
            response = client.update_document_by_text(dataset_id, required_string(parameters, "document_id"), payload)
        else:
            response = client.create_document_by_text(dataset_id, payload)
        document = response.get("document") or {}
        return {"dataset_id": dataset_id, "document_id": document.get("id"), "batch": response.get("batch"), "result": document}
    if operation == "get_indexing_status":
        batch = required_string(parameters, "batch")
        response = client.get_indexing_status(dataset_id, batch)
        records = response.get("data") or []
        completed = bool(records) and all(record.get("indexing_status") == "completed" for record in records)
        finished = bool(records) and all(record.get("indexing_status") in ("completed", "error") for record in records)
        return {"dataset_id": dataset_id, "batch": batch, "count": len(records), "completed": completed, "finished": finished, "has_errors": any(record.get("indexing_status") == "error" for record in records), "result": records}
    raise ValueError(f"Unknown operation: {operation}")
