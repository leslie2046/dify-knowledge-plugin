from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from provider.dify_knowledge_api import DifyKnowledgeClient


class DifyKnowledgeProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        try:
            base_url = str(credentials.get("base_url") or "").strip()
            api_key = str(credentials.get("api_key") or "").strip()
            client = DifyKnowledgeClient(base_url=base_url, api_key=api_key)
            client.list_datasets(limit=1)
        except Exception as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc
