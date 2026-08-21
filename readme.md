## 项目概述

数据库型 RAG Text-to-SQL 系统：用户自然语言问题 → LangGraph 工作流 → SQL → 在数仓（dw 库）执行并流式返回结果。

- 后端：FastAPI + LangGraph（`main.py` 为入口），SSE 流式响应
- 前端：Vue 3 + Vite，目录名 `data-agent-fronted`（注意拼写是 "fronted"）
- 包管理：uv（`pyproject.toml` + `uv.lock` + `.venv`），Python >= 3.12
- LLM：通义千问（OpenAI 兼容协议），Embedding：本地 TEI 容器跑 bge-large-zh-v1.5

## 常用命令

```bash
# 启动后端（uvicorn reload，127.0.0.1:8000）
python main.py

# 启动前端（vite 代理 /api → localhost:8000）
cd data-agent-fronted && npm run dev

# 构建/重建元知识库（表、字段、指标、字段值索引）
python -m app.scripts.build_meta_knowledge -c conf/meta_config.yml

# 单独调试 LangGraph 图（graph.py 的 __main__ 内置测试 query，需自行改 input）
python -m app.agent.graph

# 启动依赖的基础设施（mysql 3307 / es 9200 + kibana / qdrant 6333 / embedding 9100）
docker compose -f doc/docker/docker-compose.yaml up -d
```

所有模块必须用 `python -m app.xxx` 从仓库根目录运行（代码内 `from app.xxx` 导入依赖 cwd 在仓库根，直接 `python app/scripts/xxx.py` 会 ModuleNotFoundError）。

## 架构

### LangGraph 主链路（app/agent/graph.py）

```
START → extract_keywords
      → recall_column / recall_metric / recall_column_value（三路并行，LLM 扩展关键词后向量/全文召回）
      → merge_retrieved（合并召回结果，从 meta 库补全指标涉及的字段）
      → filter_table / filter_metric（并行，LLM 过滤无关信息）
      → add_extra_context（注入当前日期/季度等 date_info 和 dw 库版本/方言 db_info）
      → generate_sql（元信息 YAML 拼入 prompt 生成 SQL）
      → validate_sql →（条件路由）
          无错 → execute_sql → END
          有错且 retry_count < 3 → correct_sql → validate_sql
          有错且 retry_count >= 3 → END（防死循环）
```

- `validate_sql` 用 `EXPLAIN {sql}` 校验语法，**不真正执行** SQL；只有 `execute_sql` 节点真正执行
- 各节点通过 `runtime.stream_writer` 输出自定义事件（`{'type': 'progress'|'result', ...}`），经 `stream_mode='custom'` 由 `QueryService.query()` 封装成 `data: {...}\n\n` 的 SSE 流给前端
- 图状态：`app/agent/state.py` 的 `DataAgentState`；跨节点依赖（repositories、embedding client）通过 `app/agent/context.py` 的 `DataAgentContext` 注入

### 分层

- `app/clients/`：外部客户端单例管理器（embedding / es / meta+dm mysql / qdrant），在 `main.py` lifespan 中统一 init/close
- `app/repositories/`：数据访问层，按存储划分 —— `mysql/meta`（元数据库）、`mysql/dw`（数仓）、`qdrant/`（column/metric/value 三个 collection）、`es/`（字段值全文索引）
- `app/services/`：`QueryService`（跑图 + SSE 流）、`MetaKnowledgeService`（构建元知识）
- `app/entities/`：图状态中传递的纯 dataclass（ColumnInfo、MetricInfo、ValueInfo、TableInfo 等）；`app/models/`：meta 库的 SQLAlchemy ORM
- `app/agent/nodes/`：每节点一个文件；`app/agent/llm/llm.py`：全局单例 LLM
- prompt 模板在 `doc/prompts/*.prompt`，通过 `app/prompt_loader/load_prompt.py` 按文件名加载

### 双库 + 混合索引（核心机制）

- **meta 库**：存储表/字段/指标元数据（ORM 见 `app/models/`）
- **dw 库**：星型数仓，事实表 `fact_order` + 维表 `dim_*`，SQL 实际执行目标
- **元知识构建**：`conf/meta_config.yml` 定义表、字段（含 alias 同义词）、指标；构建脚本将元数据写入 meta 库，并为每个字段/指标的 name/description/alias **各生成一个 Qdrant 向量点**（uuid5 确定性 ID，可重复构建）
- 字段的 `index_type`（none/es/vector/both）决定**字段值**的索引方式，语义见 `app/conf/meta_config.py` 顶部 docstring：es=高基数专有名词精确匹配，vector=低基数口语化枚举需语义对齐，both=双路构建

### 配置

- `conf/app_config.yml` → `app/conf/app_config.py`（OmegaConf 加载为 dataclass）。**包含真实的 LLM api_key，已提交入库；勿泄露、修改前先问**
- 数据库端口非默认（MySQL 3307），均由 docker-compose 暴露

## 注意事项

- 日志用 loguru，`app/core/log.py` 的 `init_logger()` 必须在入口**显式调用**（main.py / 脚本 / graph 调试各自调用）；request_id 通过 contextvar（`app/core/context.py`）注入每条日志
- `temp_debug/` 是每次查询的调试输出，已 gitignore；`logs/` 为运行日志
