# 🗺️ AI 本地路线智能规划

> 基于 LangGraph + LangChain 构建的本地智能路线规划系统，结合高德地图 POI 数据、UGC 评价语料与用户个性偏好，自动生成可直接执行的个性化路线方案。

**赛题：现在就出发 — AI 本地路线智能规划**

---

## ✨ 核心能力

### 路线生成
- 根据用户意图自动搜索并串联多个 POI，生成完整一日游路线
- 高德地图路径规划 API（驾车 / 公交 / 步行）构建真实距离矩阵
- 贪心 TSP 算法 + LLM 偏好重排，输出地理合理的访问顺序
- 地图可视化：带编号的彩色标记 + 路线连线（驾车蓝 / 公交金 / 步行紫）

### 多条件与个性化
- 12 种游玩偏好标签（历史文化、美食、网红打卡、亲子、夜生活…）
- 自由文本输入（"想吃热干面不排队"）经 LLM 意图解析后影响 POI 筛选
- 预算范围约束，LLM 生成方案时考虑费用效率
- 出发地点支持：高德地理编码定位，作为 TSP 起点优化路线
- 用户偏好画像（ChromaDB 持久化），跨会话积累历史偏好

### UGC 评价增强
- LLM 模拟生成大众点评风格的 UGC 评价（含评分、标签、情感）
- 基于评价计算热度分、排队时间估算，影响 POI 筛选权重
- ChromaDB 向量存储缓存评价，同城 POI 复用

### 实时体验
- SSE 流式响应，实时展示每个阶段进度（POI 搜索 → 路线优化 → 方案生成）
- Unsplash API 自动为每个 POI 匹配实景照片
- LangSmith 全链路追踪，可观测每次规划的 LLM 调用详情

---

## 🏗️ 系统架构

```
用户输入（城市 / 日期 / 偏好 / 出发地 / 预算）
        │
        ▼
  POST /api/trip/plan/local/stream  ──── SSE 事件流 ────▶ 前端实时进度
        │
        ├─ 1. 高德 POI 搜索（按偏好关键词，最多 3 轮）
        │
        ├─ 2. 路线优化
        │      ├─ 高德路径规划 API → 距离/时间矩阵
        │      ├─ 贪心 TSP 排序（从出发点出发）
        │      └─ 优化指标计算（时间效率 / 费用效率 / 偏好匹配 / 路线合理性）
        │
        ├─ 3. Unsplash 实景图片（按 POI 类别英文关键词搜索）
        │
        ├─ 4. LLM 生成路线方案
        │      ├─ 餐饮推荐（早 / 午 / 晚）
        │      ├─ 路线取舍说明
        │      └─ 总体建议
        │
        └─ 5. complete 事件 → 前端跳转结果页
```

---

## 🛠️ 技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| 后端框架 | FastAPI + uvicorn | 异步 Web 服务 |
| AI 框架 | LangChain + LangGraph | LLM 编排 / Agent 图 |
| LLM | DeepSeek / Qwen（通义千问） | 意图解析、方案生成、评价模拟 |
| 地图服务 | 高德地图 API | POI 搜索、路径规划、地理编码 |
| 向量存储 | ChromaDB | 用户偏好 / POI 评价持久化 |
| 可观测性 | LangSmith | LLM 调用链路追踪 |
| 图片服务 | Unsplash API | POI 实景照片 |
| 前端框架 | Vue 3 + TypeScript | 响应式 UI |
| UI 组件 | Element Plus | 表单 / 时间线 / 进度 |
| 状态管理 | Pinia | 跨页面数据共享 |
| 地图渲染 | 高德地图 JS API | 标记 / Polyline / InfoWindow |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
```

编辑 `.env`：

```env
# LLM（至少配置一个）
DEEPSEEK_API_KEY=your_key
ALIYUN_DASHSCOPE_API_KEY=your_key

# 高德地图（必需）
AMAP_API_KEY=your_web_api_key

# LangSmith（可选，推荐）
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=trip-planner-agent

# Unsplash（可选）
UNSPLASH_ACCESS_KEY=your_key
```

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 前端

```bash
cd frontend
npm install
```

编辑 `.env`：

```env
VITE_AMAP_KEY=your_js_api_key
```

> 高德地图需分别申请 Web 服务 API Key（后端）和 JS API Key（前端）

```bash
npm run dev
```

访问 http://localhost:5173

---

## 📖 使用说明

### 本地路线规划（核心功能）

1. 选择「📍 本地路线规划」模式
2. 填写本地城市、游玩日期
3. 可选填出发地点（如"武汉火车站"）
4. 勾选游玩偏好，填写额外要求（如"想吃热干面不排队"）
5. 设置预算范围、期望去几个地方
6. 选择 AI 模型，点击「生成智能路线」
7. 实时查看规划进度
8. 结果页查看：地图路线 + 路线时间线 + 实景图片 + 餐饮推荐

### 旅行行程规划

多日跨城旅行规划，支持酒店推荐、天气查询、每日行程安排。

### 对话模式

自然语言交互，支持"帮我规划武汉一日游，想吃热干面不排队"等自由输入。

---

## 📁 项目结构

```
backend/app/
├── api/routes/
│   ├── trip.py          # 本地路线 + 旅行规划 SSE 接口
│   ├── chat.py          # 对话模式接口
│   ├── map.py           # 高德地图代理
│   └── config.py        # LLM 提供商配置
├── agents/
│   ├── graph.py         # LangGraph 图定义（双模式）
│   └── nodes/           # 各 Agent 节点
├── services/
│   ├── amap_service.py  # 高德地图（POI / 路径 / 天气 / 地理编码）
│   ├── route_service.py # 距离矩阵 + TSP 路线优化
│   ├── unsplash_service.py  # 实景图片
│   ├── review_service.py    # LLM 模拟 UGC 评价
│   ├── preference_service.py # 用户偏好画像
│   └── embedding_service.py  # ChromaDB 向量存储
├── core/
│   ├── llm.py           # LLM 工厂（DeepSeek / Qwen / OpenAI）
│   ├── config.py        # 环境变量配置
│   └── memory.py        # 对话记忆
└── models/schemas.py    # 全量 Pydantic 数据模型

frontend/src/
├── views/
│   ├── Home.vue         # 首页：双模式表单 + SSE 进度
│   ├── Result.vue       # 结果页：地图 + 路线 + 图片 + 指标
│   └── Chat.vue         # 对话模式
├── stores/trip.ts       # 路线数据状态管理
└── services/api.ts      # HTTP + SSE 请求封装
```

---

## 🔑 API Key 申请

| 服务 | 地址 | 说明 |
|---|---|---|
| 高德地图 | https://console.amap.com | 需分别申请 Web API Key 和 JS API Key |
| DeepSeek | https://platform.deepseek.com | 注册即可，按量计费 |
| 阿里云百炼 | https://bailian.console.aliyun.com | 通义千问，有免费额度 |
| LangSmith | https://smith.langchain.com | 免费，用于链路追踪调试 |
| Unsplash | https://unsplash.com/developers | 免费，5000次/小时 |
