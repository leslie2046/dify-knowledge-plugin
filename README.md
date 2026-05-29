# Dify Knowledge Plugin

Tool plugin for listing Dify knowledge bases, listing knowledge-base documents, and retrieving chunks through the official Knowledge API.

## Tool

- `list_datasets`: list Dify knowledge bases with optional keyword, pagination, permission, and tag filters.
- `list_documents`: list documents in a specific knowledge base with optional keyword, status, and pagination filters.
- `retrieve_chunks`: search a Dify knowledge base and return normalized chunk results.

## List Datasets Parameters

- `keyword`: optional name filter.
- `page`: optional page number, defaults to `1`.
- `limit`: optional page size, defaults to `20`.
- `include_all`: optional flag to include all knowledge bases regardless of permissions.
- `tag_ids`: optional comma-separated or JSON array list of tag ids.

## Credentials

- `Base URL`: Dify Knowledge API base URL. The plugin accepts `https://your-dify-host/v1` directly and also normalizes a host URL like `https://your-dify-host` to `/v1`.
- `API Key`: Dify Service API key with knowledge base access.

## List Documents Parameters

- `dataset_id`: required knowledge base id.
- `keyword`: optional document-name filter.
- `status`: optional status filter.
- `page`: optional page number, defaults to `1`.
- `limit`: optional page size, defaults to `20`.

## Parameters

- `query`: required search query.
- `dataset_id`: required knowledge base id.
- `search_method`: optional override for internal knowledge bases.
- `top_k`: optional override for result count.
- `score_threshold_enabled` / `score_threshold`: optional score filtering overrides.
- `reranking_enable` / `reranking_mode`: optional reranking overrides for internal knowledge bases.
- `reranking_provider_name` / `reranking_model_name`: required when reranking mode is `reranking_model`.
- `weight_type` / `vector_weight` / `keyword_weight`: optional hybrid-search weight overrides.
- `attachment_ids`: optional comma-separated or JSON array list of attachment ids.

## Notes

- The tool first fetches knowledge base details, then merges your overrides on top of the current retrieval configuration. This avoids accidentally replacing the knowledge base defaults when you only want to change a single field such as `top_k`.
- For external knowledge bases, only `top_k` and score-threshold overrides are applied. Internal-only options such as `search_method` or reranking configuration are rejected.

## Development

```bash
python -m compileall main.py provider tools tests
python -m unittest discover -s tests
```
