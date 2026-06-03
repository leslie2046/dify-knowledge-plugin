import json
import logging
from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.config.logger_format import plugin_logger_handler
from dify_plugin.entities.tool import ToolInvokeMessage

from provider.dify_knowledge_api import DifyKnowledgeClient
from provider.dify_knowledge_utils import (
    build_retrieve_payload,
    normalize_retrieval_response,
    select_dataset_id,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if plugin_logger_handler not in logger.handlers:
    logger.addHandler(plugin_logger_handler)


class RetrieveChunksTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        credentials = self.runtime.credentials or {}

        try:
            client = DifyKnowledgeClient(
                base_url=str(credentials.get("base_url") or "").strip(),
                api_key=str(credentials.get("api_key") or "").strip(),
            )
            dataset_id = select_dataset_id(tool_parameters=tool_parameters)
            payload = build_retrieve_payload(tool_parameters=tool_parameters)
            logger.info(
                "Dify knowledge retrieve request dataset_id=%s payload=%s",
                dataset_id,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            )
            response_data = client.retrieve_chunks(dataset_id=dataset_id, payload=payload)
            yield self.create_json_message(normalize_retrieval_response(response_data, dataset_id))
        except Exception as exc:
            raise ValueError(f"Dify knowledge retrieval failed: {exc}") from exc
