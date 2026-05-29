from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.dify_knowledge_utils import (
    build_retrieve_payload,
    normalize_retrieval_response,
    select_dataset_id,
)


class RetrieveChunksTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}

        try:
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            dataset_id = select_dataset_id(tool_parameters=tool_parameters)
            dataset_details = client.get_dataset(dataset_id)
            payload = build_retrieve_payload(tool_parameters=tool_parameters, dataset_details=dataset_details)
            response_data = client.retrieve_chunks(dataset_id=dataset_id, payload=payload)
            yield self.create_json_message(normalize_retrieval_response(response_data, dataset_id))
        except Exception as exc:
            raise ValueError(f"Dify knowledge retrieval failed: {exc}") from exc
