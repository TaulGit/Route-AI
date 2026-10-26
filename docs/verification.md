# 本地验收记录

日期：2026-10-26。本页记录本地验收；远端 CI 请查看仓库 Actions，独立作品集发布不等于实时规划服务已部署。

| 验证 | 实际结果 | 证明范围 |
|---|---|---|
| `backend/.venv/bin/python -m pytest -q` | **56 passed** | 真实图调度、tool-call 协议 fake、约束、持久运行器、HTTP API |
| `PYTHONPATH=backend backend/.venv/bin/python -m evals.run` | **17/17 场景、109/109 检查** | 固定场景下的编排/规则行为；报告见 `eval-report.json` |
| `cd frontend && npm run build` | **通过**，包含全项目 `vue-tsc --noEmit` | 类型检查与生产构建；有既有大 chunk 和混合 import 提示 |
| `npm audit` | **0 vulnerabilities** | 本次安装时 npm registry 返回的依赖审计；未做渗透测试 |
| Chrome 本地页面 | **生成 → 待审核 → 刷新自动恢复 → 确认完成** | 离线武汉示例完整前后端交互，6 个来源候选、3 个选中地点；fixture 345 分钟/130 元，不是实时出行测量 |
| 两次独立 Python 进程 | **通过** | 第一个进程生成并退出，第二个读取相同 SQLite 检查点、批准原提案，未重新生成 |
| 运行中关停并重建 runtime | **通过** | 未完成的只读检索从检查点恢复到待审核 |
| 关闭 SSE 消费者 | **通过** | 后台任务继续，随后可用 GET 快照读取 |
| 重复/旧中断提交、跨用户 GET/resume | **通过** | CAS 冲突、旧中断 ID 拒绝、会话 owner 隔离 |
| 演示服务恢复旧 live 记录 | **通过阻断测试** | 不触发 live provider；不消耗真实密钥 |

核心版本为本地已安装并锁定的 LangGraph 1.2.17、langchain-core 1.7.0、langchain-openai 1.7.2、langgraph-checkpoint-sqlite 3.1.2。依赖见 `backend/requirements-agent.lock.txt`。

实时模式的模型、高德、Supabase 鉴权尚未进行网络集成验收；本机未配置这些凭证。预算、票价、开放时间及路线来源边界见 README 和 architecture.md。不能根据以上数据推断模型线上成功率、生产吞吐、推荐质量或用户增长。
