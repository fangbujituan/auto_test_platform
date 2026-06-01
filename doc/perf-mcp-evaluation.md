# 性能测试 MCP 自建评估

> 决策文档（Step 5 - T5.5）：评估自建 ``k6-mcp`` 或 ``locust-mcp`` 的必要性与投入产出比。
>
> 结论：**先不做**，把性能测试需求收敛到"等真实压测项目立项后再启动"。
> 当前阶段只在主 README 的开发计划里把它从 P1 降到 P2。

---

## 候选方案对比

| 方案 | 工具链 | 自建成本 | 复用现成 MCP | 与 ATP 集成度 |
|---|---|---|---|---|
| k6-mcp | k6 + InfluxDB + Grafana | 高（要包脚本生成 + 启动 + 结果回收 + 解析） | 无成熟方案 | 低（结果格式独立） |
| locust-mcp | Locust（Python 原生） | 中（Python 侧好嵌入，Web UI 已有） | 无成熟方案 | 中（同 Python 栈） |
| **手写 pytest + concurrent.futures** | 项目内已有 ``requests`` | 0 | — | 高（直接用 ApiScriptAgent 产物） |

---

## 不立即自建的 4 个理由

1. **当前主链路是 UI / API 测试**：性能测试需求未真实落项目层立项，自建的 MCP 没有调用方
2. **Token 经济性差**：性能场景 LLM 价值有限——"读 OpenAPI → 拼并发参数"是规则化任务，
   不需要大模型介入。强行套 LLM 反而绕路
3. **生态成熟度低**：目前社区没有看到生产级 k6-mcp / locust-mcp 实现，需要从头自建
4. **降级方案足够**：用 ``ApiScriptAgent`` 产 pytest 脚本 +
   ``concurrent.futures.ThreadPoolExecutor`` 就能跑出大多数场景的 RPS 报告

---

## 真要做时的 MVP 方案

如果未来性能测试立项，按以下顺序最小落地：

1. **复用 ApiScriptAgent**：让它在 prompt 里输出 Locust ``@task`` 风格脚本（template 切换即可）
2. **新增 ``perf-mcp``**：仅 3 个工具
   - ``run_locust(script_path, users, spawn_rate, duration)``
   - ``get_locust_stats(run_id)``
   - ``stop_locust(run_id)``
3. **新增 ``PerfAgent``**：继承 ``BaseAgent``，``_process`` 里调上面 3 个工具，
   把 RPS / p95 / 错误率写到 ``state.output_data``
4. **新增 ``perf_testing_workflow``**：``intent → testcase → review_gate →
   persistence → api_script(perf 模式) → perf_run → result``

整个增量约 1 周工作量，其中 LLM token 消耗与现有 ``api_script`` 持平。

---

## 当前里程碑确认

- [x] 评估完成：暂不自建 k6-mcp / locust-mcp
- [x] 主 README 中 "性能自动化 Agent + k6-mcp / locust-mcp" 保留为 P2
- [ ] 等真实压测立项后参考本文 MVP 方案启动
