# Dify 知识库检索插件

这是一个 Dify 工具类型插件，通过官方 Knowledge API 获取知识库列表、获取知识库文档列表，并检索指定知识库中的分段内容。

## 工具

- `list_datasets`：获取知识库列表，支持关键词、分页、权限范围和标签筛选。
- `list_documents`：获取指定知识库的文档列表，支持关键词、状态和分页筛选。
- `retrieve_chunks`：检索指定知识库，并返回标准化后的分段结果。

## list_datasets 参数

- `keyword`：可选，按知识库名称筛选。
- `page`：可选，页码，默认 `1`。
- `limit`：可选，每页数量，默认 `20`。
- `include_all`：可选，是否忽略权限范围并包含全部知识库。
- `tag_ids`：可选，标签 ID 列表，支持逗号分隔字符串或 JSON 数组字符串。

## 凭据配置

- `Base URL`：Dify Knowledge API 地址。既支持直接填写 `https://your-dify-host/v1`，也支持填写主机地址，由插件自动补成 `/v1`。
- `API Key`：拥有知识库访问权限的 Dify Service API Key。

## list_documents 参数

- `dataset_id`：必填，知识库 ID。
- `keyword`：可选，按文档名称筛选。
- `status`：可选，文档状态筛选。
- `page`：可选，页码，默认 `1`。
- `limit`：可选，每页数量，默认 `20`。

## 工具参数

- `query`：必填，检索问题或关键词。
- `dataset_id`：必填，知识库 ID。
- `search_method`：可选，仅内部知识库生效，用于覆盖检索方式。
- `top_k`：可选，覆盖返回结果数量。
- `score_threshold_enabled` / `score_threshold`：可选，覆盖相似度阈值过滤配置。
- `reranking_enable` / `reranking_mode`：可选，仅内部知识库生效，用于覆盖重排配置。
- `reranking_provider_name` / `reranking_model_name`：当 `reranking_mode` 为 `reranking_model` 时需要提供。
- `weight_type` / `vector_weight` / `keyword_weight`：可选，用于 Hybrid Search 权重覆盖。
- `attachment_ids`：可选，支持逗号分隔字符串或 JSON 数组字符串。

## 实现说明

- 工具会先读取知识库详情，再把本次调用的覆盖参数合并到知识库当前检索配置上。这样在你只想修改 `top_k` 之类单个字段时，不会把知识库原有的 `search_method`、rerank 等设置意外覆盖掉。
- 如果目标是外部知识库，只会应用 `top_k` 和相似度阈值相关覆盖；`search_method`、rerank、hybrid 权重等内部知识库专用参数会直接报错。

## 本地校验

```bash
python -m compileall main.py provider tools tests
python -m unittest discover -s tests
```
