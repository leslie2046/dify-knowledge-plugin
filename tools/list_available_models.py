from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.dify_knowledge_utils import (
    build_list_available_models_params,
    normalize_available_models_response,
)


class ListAvailableModelsTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}

        try:
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            params = build_list_available_models_params(tool_parameters)
            response_data = client.list_available_models(model_type=params["model_type"])
            yield self.create_json_message(
                normalize_available_models_response(response_data=response_data, model_type=params["model_type"])
            )
        except Exception as exc:
            raise ValueError(f"Dify available models lookup failed: {exc}") from exc
