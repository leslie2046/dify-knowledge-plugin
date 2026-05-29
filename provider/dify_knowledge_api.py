from __future__ import annotations

from typing import Any

import requests

from provider.dify_knowledge_utils import normalize_base_url


class DifyKnowledgeApiError(RuntimeError):
    """Raised when the Dify Knowledge API returns an error."""


class DifyKnowledgeClient:
    def __init__(self, base_url: str, api_key: str, timeout: int = 60) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key.strip()
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("api_key is required")

    def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        keyword: str | None = None,
        include_all: bool | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if keyword:
            params["keyword"] = keyword
        if include_all is not None:
            params["include_all"] = include_all
        if tag_ids:
            params["tag_ids"] = tag_ids
        return self._request("GET", "/datasets", params=params)

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._request("GET", f"/datasets/{dataset_id}")

    def list_documents(
        self,
        dataset_id: str,
        *,
        page: int = 1,
        limit: int = 20,
        keyword: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if keyword:
            params["keyword"] = keyword
        if status:
            params["status"] = status
        return self._request("GET", f"/datasets/{dataset_id}/documents", params=params)

    def retrieve_chunks(self, dataset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/datasets/{dataset_id}/retrieve", json_body=payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                params=params,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise DifyKnowledgeApiError(str(exc)) from exc

        if response.status_code >= 400:
            raise DifyKnowledgeApiError(self._format_error_response(response))

        try:
            return response.json()
        except ValueError as exc:
            raise DifyKnowledgeApiError(f"Unexpected non-JSON response from {url}") from exc

    def _format_error_response(self, response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}

        parts = [f"HTTP {response.status_code}"]

        for key in ("message", "detail", "error", "code"):
            value = payload.get(key)
            if value:
                parts.append(str(value))

        if len(parts) == 1:
            text = response.text.strip()
            if text:
                parts.append(text[:300])

        return ": ".join(parts)
