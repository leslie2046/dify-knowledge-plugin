from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.dify_knowledge_utils import (
    build_list_segments_params,
    normalize_segment_list_response,
    select_dataset_id,
    select_document_id,
)


class ListSegmentsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}
        try:
            dataset_id = select_dataset_id(tool_parameters)
            document_id = select_document_id(tool_parameters)
            params = build_list_segments_params(tool_parameters)
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            response_data = client.list_segments(dataset_id=dataset_id, document_id=document_id, **params)
            yield self.create_json_message(normalize_segment_list_response(response_data, dataset_id, document_id))
        except Exception as exc:
            raise ValueError(f"Dify knowledge list segments failed: {exc}") from exc
