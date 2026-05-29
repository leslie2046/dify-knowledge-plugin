from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.dify_knowledge_utils import (
    build_list_documents_params,
    normalize_document_list_response,
    select_dataset_id,
)


class ListDocumentsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}

        try:
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            dataset_id = select_dataset_id(tool_parameters=tool_parameters)
            params = build_list_documents_params(tool_parameters)
            response_data = client.list_documents(dataset_id=dataset_id, **params)
            yield self.create_json_message(normalize_document_list_response(response_data, dataset_id))
        except Exception as exc:
            raise ValueError(f"Dify knowledge list documents failed: {exc}") from exc
