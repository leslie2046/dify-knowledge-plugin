from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.knowledge_operations import invoke_operation


class GetIndexingStatusTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}
        try:
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            yield self.create_json_message(invoke_operation(client, "get_indexing_status", tool_parameters))
        except Exception as exc:
            raise ValueError(f"Dify knowledge get_indexing_status failed: {exc}") from exc
