from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.knowledge_operations import invoke_operation


class RetrieveMultipleTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}
        try:
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            yield self.create_json_message(invoke_operation(client, "retrieve_multiple", tool_parameters))
        except Exception as exc:
            raise ValueError(f"Dify knowledge retrieve_multiple failed: {exc}") from exc
