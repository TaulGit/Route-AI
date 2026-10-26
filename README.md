# RouteAI — 可恢复的多 Agent 旅行规划

基于 **LangGraph 1.2 + FastAPI + Vue 3** 的一日游规划工作台。新主流程将需求澄清、并行工具检索、结构化提案、确定性校验和用户审核连接成可恢复的工作流。

## 当前实现

- **Coordinator–Worker**：主管拆分最多 3 个研究任务，`Send` 分发独立上下文的检索 Agent；每个 Agent 在模型与 `search_poi` 工具之间循环，最多 3 次模型和 3 次工具尝试。
- **持久化 HITL**：SQLite checkpointer + `interrupt/Command(resume=...)`，缺信息时澄清，提案生成后等待审核，支持修改、拒绝、刷新恢复和进程重启后续跑。
- **证据约束**：模型只能选择已检索的 POI ID；坐标、名称、来源和时间由工具结果提供。新主流程不生成模拟 UGC，不把模型编造的地点补作“兜底”。
- **有界修复**：代码检查地点引用、重复地点、景点数、连续交通、时间和估算预算；最多 2 次修复，仍不满足则明确失败。
- **真实进度**：从实际节点边界生成 SSE，写入持久事件日志；页面刷新后以服务端快照恢复。浏览器断开不会取消后台任务。
- **可重复评测**：真实 LangGraph + scripted providers 的离线场景集，另有工具循环、SQLite 恢复、鉴权、重复审核和断流测试。

新前端在 `/` 或 `/agent`，原 UI 保留在 `/classic`。原聊天、多日游和向量画像属于经典实现，见 [经典版说明](docs/legacy.md)。

## 公开作品案例

- [Taul 的作品集](https://taulgit.github.io/portfolio.html)
- [RouteAI 案例与离线执行回放](https://taulgit.github.io/portfolio/routeai.html)：无需登录即可查看真实图执行记录；为固定数据回放，不调用实时模型或地图。
- 回放数据来自真实离线图运行，可在仓库根目录重新导出：`PYTHONPATH=backend backend/.venv/bin/python backend/scripts/export_portfolio.py`，生成 `docs/portfolio-demo.json`。

## 本地体验（无需 API Key）

需要 **Python 3.12、Node.js 22**。系统 Python 3.8 不适用。

```bash
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-agent.lock.txt
cd backend
ROUTEAI_DEMO=true .venv/bin/uvicorn app.api.agent_app:app --host 127.0.0.1 --port 8000
```

另一个终端：

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173/`。用武汉示例生成行程，刷新后继续审核；清空城市或预算可体验澄清；修改偏好后可重新规划。

`ROUTEAI_DEMO=true` 是显式的**本地演示开关**：使用固定武汉数据，模型/外部工具请求为 0，演示身份为 `local-demo`。它会拒绝创建、恢复实时任务，也不会自动恢复旧 live 任务。默认关闭，不用于共享部署。不要把示例结果当作实时票价或路况。

## 实时模式

1. 复制 `backend/.env.example` 为 `backend/.env`，设置 `ROUTEAI_DEMO=false`、高德 Web 服务 Key、至少一个模型 Key、Supabase URL/Anon Key。前端的 Supabase 环境变量见 `frontend/src/lib/supabase.ts`。
2. 在 `backend/` 启动同一 `app.api.agent_app:app` 入口，前端登录后选择“实时规划”。模型需支持原生 tool calling；结构化输出使用 `with_structured_output(..., method="function_calling")`，不假定每个兼容服务都支持 provider-native JSON Schema。
3. 需原多日游/聊天等 API 时，安装 `backend/requirements.txt`，改用 `app.api.main:app`；该兼容入口也注册了新 Agent API。仅安装 v3 依赖的独立服务不提供经典 API。

新服务默认使用 `backend/data/agent.sqlite3`（相对于后端工作目录），通过 `AGENT_DB_PATH` 可改为持久卷路径。只支持 **单个后端进程、单个 worker**。Docker/Railway 入口已指向 v3；云环境需挂载持久存储。配置和 Dockerfile 已更新，本次未执行云部署或容器构建。

新链路只查询选中行程的相邻路段，无候选全量距离矩阵。高德失败时明确标为 `estimate`。预算校验只针对当前估算：门票 0 可表示未核实，不保证实际总价；尚未验证开放时间、预约名额、起终点接驳和天气可行性。

## 验证与可复现报告

在仓库根目录：

```bash
backend/.venv/bin/python -m pytest -q
PYTHONPATH=backend backend/.venv/bin/python -m evals.run
cd frontend
npm run build
```

- [离线评测报告](docs/eval-report.json)：**17/17 场景、109/109 检查**；无网络、使用 scripted providers，不测真实模型质量、API 健康度或线上成功率。
- `backend/tests/test_v3_providers.py`：真实消息/tool 协议上的 fake 模型与 fake 高德，覆盖空结果改词、参数拒绝、调用上限、超时和显式估算。
- `backend/tests/test_v3_runtime.py`：SQLite、两次独立 Python 进程恢复、浏览器断流、审核幂等保护、用户隔离和 HTTP 接口。
- `backend/tests/test_v3_workflow.py`：真实图调度，包含必须由两个 worker 同时到达才能释放的并行屏障。
- `.github/workflows/agent-checks.yml` 提供离线 CI 配置；本地通过不等于 GitHub Actions 已执行。

本次已完成浏览器离线演示的生成、刷新恢复与确认；**未配置/调用真实 LLM、高德和 Supabase，未进行线上发布**。实时 API 集成已实现，实际服务兼容性需配置密钥后检验。

指标口径：`tool_calls/model_calls` 是已返回并持久化节点记录的逻辑请求/尝试数，不是供应商 HTTP 请求数或账单；`elapsed_seconds` 累计已结束执行段的时间，不含人工等待，也不能完整统计崩溃前未落盘的执行。节点中的只读检索可能在故障恢复时重放，不宣称 exactly-once。

## 代码入口与项目材料

| 路径 | 用途 |
|---|---|
| `backend/app/agents/v3/models.py` | 需求、证据、结构化提案与 API 契约 |
| `backend/app/agents/v3/workflow.py` | 状态图、并行归并、澄清、校验与修复 |
| `backend/app/agents/v3/providers.py` | 原生工具循环、模型/高德适配、离线数据 |
| `backend/app/agents/v3/runtime.py` | 检查点、后台执行、事件日志与恢复 |
| `backend/app/api/agent_app.py` | 不依赖经典 Chroma 栈的独立入口 |
| `frontend/src/views/Agent.vue` | 新版工作台 |
| [架构与面试复盘](docs/architecture.md) | 技术选择、官方来源和能力边界 |
| [简历新版](docs/resume.md) | 可直接使用的项目经历和表述依据 |
