# Dify 知识库插件

这是一个面向 Dify Knowledge API 的工具插件，用于查看和检索知识库、读取文档分段、写入文本知识、查询索引状态，以及获取元数据、标签和可用模型。

version: 0.1.0
author: [leslie2046](https://github.com/leslie2046)
repo: [leslie2046/dify-knowledge-plugin](https://github.com/leslie2046/dify-knowledge-plugin)

## 功能

- `list_datasets`：获取知识库列表，支持关键词、分页、权限范围和标签筛选。
- `list_documents`：获取指定知识库的文档列表，支持关键词、状态和分页筛选。
- `list_segments`：分页读取文档分段，支持关键词和索引状态筛选。
- `get_segment`：按分段 ID 读取单个分段的详细内容。
- `retrieve_chunks`：检索指定知识库，并返回标准化后的分段结果。
- `list_available_models`：按模型类型查询 Dify 可用模型，尤其适合知识库配置前查看 `text-embedding` 和 `rerank` 模型。
- `get_dataset`：获取知识库详情、配置和统计信息。
- `list_metadata_fields`：查询元数据字段名称、类型、使用数量和内置字段启用状态。
- `list_tags`：查询工作区知识库标签及 ID。
- `create_document_by_text`：创建文本知识文档，返回索引批次。
- `update_document_by_text`：更新已有文档的正文、名称或处理配置。
- `get_indexing_status`：查询文档批次的处理状态。
- `retrieve_multiple`：联合检索最多 20 个知识库，返回去重结果、来源和各库错误。

## 凭据配置

- `Base URL`：Dify Knowledge API 地址。既支持直接填写 `https://your-dify-host/v1`，也支持只填写主机地址，插件会自动补成 `/v1`。
- `API Key`：具有目标工作区知识资源访问权限的 Dify Service API Key。
- `验证用知识库 ID`：可选。限定知识库范围的 API Key 请填写授权范围内的知识库 ID，插件会使用详情接口验证。`list_datasets`、`list_tags`、`list_available_models` 等工作区级工具需要可访问全部知识库的 Key。

### 获取凭据

在 Dify 中打开“服务 API”面板，将 API 端点复制到插件的 `Base URL` 字段。

![复制 Dify 服务 API 端点](./_assets/get_credentials_base_url.png)

点击“API 密钥”，然后在弹窗中点击“创建密钥”。

![创建 Dify Service API Key](./_assets/get_credentials_create_api_key.png)

选择“所有知识库”以使用全部工具，或选择“指定知识库”限制访问范围。指定知识库的密钥还需要在插件的“验证用知识库 ID”中填写授权范围内的知识库 ID。然后点击“创建”。

![选择知识库访问权限](./_assets/get_credentials_api_key_scope.png)

复制新创建的密钥，填入插件的 `API Key` 字段。

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

### `list_segments`

直接读取已存储的文档分段，适合阅读指定文档、总结内容和检查分段情况。

- `dataset_id`、`document_id`：必填。文档 ID 可通过 `list_documents` 或 `retrieve_chunks` 获取。
- `keyword`：可选，按分段内容筛选。
- `status`：可选，分段索引状态列表，支持逗号分隔或 JSON 数组字符串，例如 `completed,indexing,error`。这里不是 `available` 等文档显示状态。
- `page`、`limit`：可选，默认 `1` 和 `20`，每页最多 `100` 个分段。
- 输出：文档分段模式 `doc_form`、分页信息（`page`、`limit`、`total`、`has_more`）、`count` 和 `result` 数组。每个分段保留正文、问答答案、位置、索引状态、启用状态，以及接口返回的附件和子分段，并提供 `dataset_id`、`document_id`、`segment_id`。

总结整篇文档时，请留空关键词和状态筛选，根据 `has_more` 继续读取后续页，并按 `position` 整理内容。单页不一定包含整篇文档。问答模式下，问题正文 `content` 和答案 `answer` 分别保留。

### `get_segment`

- `dataset_id`、`document_id`、`segment_id`：必填。可使用 `list_segments` 或 `retrieve_chunks` 返回的 ID。
- 输出：`dataset_id`、`document_id`、`doc_form` 和包含分段详情的 `result` 对象。

适合查看已知分段的内容和索引状态，无需再次执行相似度检索。此工具只返回一个分段；浏览同一文档的其他分段请使用 `list_segments`。

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
- `metadata_filtering_conditions`：可选 JSON 对象，在内部知识库检索前按文档元数据过滤。字段名称可通过 `list_metadata_fields` 查询。

提供覆盖参数或元数据过滤条件时，插件会读取知识库原配置后合并修改。仅设置 `top_k` 会保留原检索方式、重排模型和权重。显式关闭阈值时，以关闭设置为准。外部知识库支持数量和阈值覆盖；内部专用覆盖参数和元数据过滤会报错。

元数据过滤示例：

```json
{"logical_operator":"and","conditions":[{"name":"department","comparison_operator":"is","value":"support"}]}
```

支持字符串比较（如 `is`、`contains`、`empty`）、字符串数组匹配（`in`、`not in`）、数值比较和时间比较（`before`、`after`，使用数值时间戳）。`!=`、`>=`、`<=` 会转换为 API 使用的 Unicode 运算符。

### `get_dataset`、`list_metadata_fields`、`list_tags`

- `get_dataset`：必填 `dataset_id`，在 `result` 中返回详情，包含 API 原始字段 `retrieval_model_dict`。
- `list_metadata_fields`：必填 `dataset_id`，返回 `count`、字段数组 `result` 和 `built_in_field_enabled`。
- `list_tags`：无需参数，返回 `count` 和标签数组 `result`。标签 ID 可用于 `list_datasets.tag_ids`。

### `create_document_by_text`、`update_document_by_text`

这两个工具会写入知识库。创建必填 `dataset_id`、`name`、`text`；更新还需要已有文档的 `document_id`，并至少提供一个修改字段。更新正文时需要同时提供 `name`。

- 共同可选参数：`doc_form`、`doc_language`、`process_rule`（JSON 对象）、`retrieval_model`（完整 JSON 对象）。
- 创建还支持 `indexing_technique`、`embedding_model`、`embedding_model_provider`。知识库未配置索引方式时，首篇文档需要指定 `indexing_technique`。
- 创建默认自动处理；更新时省略处理配置可保留原设置。父子分段模式需要 `hierarchical` 处理规则及 `rules` 对象。
- 返回 `dataset_id`、`document_id`、`batch` 和文档记录 `result`。写入不自动重试或去重，重复调用创建工具可能产生重复文档。

### `get_indexing_status`

必填 `dataset_id` 和创建或更新返回的 `batch`。返回处理记录 `result`、`count`、`completed`（全部成功）、`finished`（全部进入完成或错误状态）和 `has_errors`。每次调用查询一次，工作流可设置间隔和超时进行轮询；暂停状态不算完成。

### `retrieve_multiple`

- `dataset_ids`：必填，逗号分隔或 JSON 数组字符串，支持 1–20 个不同知识库 ID。
- `query` 及可选检索参数：与 `retrieve_chunks` 相同。未覆盖时，各库保留自己的原配置；过滤条件涉及的元数据字段需要在各目标库中存在。
- `max_results`：跨库去重后返回数量上限，默认 `20`，范围 `1–200`；`top_k` 仍是每个知识库的检索数量。
- 输出：`result`、`count`、`total_count`（截断前的已检索唯一结果数）、`has_more`（结果被上限截断）、`partial_failure`、`errors` 和 `ordering`。

最多同时检索四个知识库。按照输入库顺序和各库内部排名交替输出，不比较跨库分数，不执行全局重排。相同正文和答案的结果去重，全部来源及分数保留在 `sources` 中。部分失败时保留成功结果；全部失败时抛错。`has_more` 不代表接口分页，也不保证还有其他可检索内容。

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
