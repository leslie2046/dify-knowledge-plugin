# Dify 知识库插件

这是一个面向 Dify Knowledge API 的工具插件，用于查看知识库、查看文档、检索分段内容，以及查询知识库配置可用模型。

## 功能

- `list_datasets`：获取知识库列表，支持关键词、分页、权限范围和标签筛选。
- `list_documents`：获取指定知识库的文档列表，支持关键词、状态和分页筛选。
- `retrieve_chunks`：检索指定知识库，并返回标准化后的分段结果。
- `list_available_models`：按模型类型查询 Dify 可用模型，尤其适合知识库配置前查看 `text-embedding` 和 `rerank` 模型。

## 凭据配置

- `Base URL`：Dify Knowledge API 地址。既支持直接填写 `https://your-dify-host/v1`，也支持只填写主机地址，插件会自动补成 `/v1`。
- `API Key`：具有目标工作区知识资源访问权限的 Dify Service API Key。

### 获取凭据

在 Dify 中打开“服务 API”面板，将 API 端点复制到插件的 `Base URL` 字段。

![复制 Dify 服务 API 端点](./_assets/get_credentials_base_url.png)

点击“API 密钥”，在弹窗中复制密钥并填入插件的 `API Key` 字段。

![复制 Dify 服务 API Key](./_assets/get_credentials_api_key.png)

## 工具说明

### `list_datasets`

用于先确认有哪些知识库可用。

- `keyword`：可选，按知识库名称筛选。
- `page`：可选，页码，默认 `1`。
- `limit`：可选，每页数量，默认 `20`。
- `include_all`：可选，是否忽略权限范围并包含全部可见知识库。
- `tag_ids`：可选，标签 ID 列表，支持逗号分隔字符串或 JSON 数组字符串。

### 获取 `dataset_id`

在 Dify 中打开知识库，浏览器地址栏里 `/datasets/` 和 `/documents` 之间的 UUID 就是 `dataset_id`。

![Dify URL 中的 dataset_id](./_assets/get_dataset_id.png)

### `list_documents`

用于查看某个知识库下的文档。

- `dataset_id`：必填，知识库 ID。
- `keyword`：可选，按文档名称筛选。
- `status`：可选，按文档状态筛选。
- `page`：可选，页码，默认 `1`。
- `limit`：可选，每页数量，默认 `20`。

### `retrieve_chunks`

用于从指定知识库中检索相关分段。

可选检索参数只对本次请求生效，不会更改知识库中保存的配置。可选参数留空时，Dify 会使用该知识库中已保存的检索配置。

- `dataset_id`：必填，知识库 ID。
- `query`：必填，检索问题或关键词。
- `search_method`：可选，仅内部知识库生效，用于覆盖检索方式。
- `top_k`：可选，覆盖返回结果数量。
- `score_threshold_enabled` 和 `score_threshold`：可选，覆盖相似度阈值过滤配置。
- `reranking_enable` 和 `reranking_mode`：可选，仅内部知识库生效，用于覆盖重排配置。
- `reranking_provider_name` 和 `reranking_model_name`：当 `reranking_mode` 为 `reranking_model` 时必填。可选值可通过 `list_available_models` 且 `model_type=rerank` 获取。
- `weight_type`、`vector_weight` 和 `keyword_weight`：可选，用于 Hybrid Search 权重覆盖。
- `attachment_ids`：可选，支持逗号分隔字符串或 JSON 数组字符串。

### `list_available_models`

封装了 Dify 的“获取可用模型”接口：`GET /workspaces/current/models/model-types/{model_type}`。

- `model_type`：必填，支持 `text-embedding`、`rerank`、`llm`、`tts`、`speech2text`、`moderation`。
- 输出：按 provider 分组后的标准化结果，包含 `provider_count`、总 `model_count` 以及每个 provider 下的 `models` 列表。

## 说明

- `list_available_models` 主要用于在创建或更新知识库配置前，确认当前工作区有哪些 `text-embedding` 或 `rerank` 模型可用。
- `retrieve_chunks` 只有在你显式传入覆盖参数时，才会发送检索配置覆盖；这些覆盖仅对本次请求生效，不会写回知识库配置。
- `tag_ids`、`attachment_ids` 这类列表参数同时支持 `a,b,c` 形式和 `["a","b","c"]` 形式。

## 支持与反馈

如果这个插件对你有帮助，欢迎给项目点一个 Star。遇到问题、疑问或有功能建议，可以在 GitHub Issue 中反馈，并尽量附上 Dify 版本、插件版本和复现步骤。
