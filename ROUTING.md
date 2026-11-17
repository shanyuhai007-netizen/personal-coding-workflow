# 专业组件路由

WORKFLOW.md 管阶段推进。每阶段先按下表检查触发条件；适用且可用的组件须读取 / 调用原文并执行，完成条件达成才进入下一阶段。只列名称、源文件或安装成功不能算执行。

先查当前技能目录 / 工具清单及项目已有选择，避免为一个阶段加载所有组件。默认采用表内首选；已有等价组件可复用并写理由。用户显式指定的组件优先遵守其指令。

| 触发条件 | 首选组件 | 产出与出口 |
|---|---|---|
| 业务目标 / 术语影响行为但仍有歧义 | grilling / domain-modeling | 查证技术事实，真正业务决定才问用户；写决定 |
| 需要可运行答案 / 缺外部事实 | prototype / research | 实验结果或有一手引用的研究，说明限制 |
| 跨会话功能需拆分 | to-spec / to-tickets | 本地 spec、完成条件与依赖图；已有批准产物直接复用 |
| 已明确行为的可测试改动 | tdd；大型票可选 implement | 按独立契约的 red → green 切片；低风险文字改动用相称检查 |
| 多票接口清楚可隔离 | implement-spec | 隔离实现、明确集成责任方、最终树复验 |
| 报错 / 失败 / 性能回退需定位 | diagnosing-bugs | 紧反馈复现、根因、回归；性能另读 docs/BENCHMARK.md |
| HTML / CSS / 客户端 JS | modern-web-guidance | 先核实现代平台做法再修改 |
| 新 UI 设计 / 交互打磨 | frontend-design / emil-design-eng | 视觉决定与运行交互证据 |
| React / Next.js / 明确 UI 审计 | vercel-react-best-practices / web-design-guidelines | 性能或可访问性复核 |
| 缺产物验收入口 | 项目 verify；可用时 create-verification-skill | 最小启动 / doctor / drive / observe 配方并实际运行 |
| 非平凡设计落 spec / ADR 前 | 独立事实 reviewer | 核验关键来源、指标语义、单位及推论边界 |
| 非平凡改动交付前 | code-review | 覆盖最终树的 Standards / Spec 独立报告及修复结果 |
| 重复故障 / 纠正 | retro | 可复现检查或环境修复，记录效果 |
| 跨 Agent 且现有记录不足 | handoff | 当前树、证据、未完成项与下一动作 |

每个适用阶段在任务记录留下：触发原因、实际组件源文件 / hash、模式、适配版本、执行证据与产出。用 [component 工具](docs/TOOLS.md) 可封存源文件与证据；执行记录的真实性仍由调用方负责。

模式精确定义：`native` = 原生接口成功且有调用记录；`read` = 明确读原文后执行；`reuse` = 复用仍有效的既有产物并核对适用性；`degraded` = 先记录搜索范围或具体权限 / 能力限制，再执行本流程替代步骤。原生接口不可用而源文件可读时采用 read。上游仅限用户调用时遵守当前环境约束，允许的资料读取不能冒称原生调用。

降级需写明失去的保障和补验方式；必要能力缺失保持未满足。当前环境 / 用户指令优先，具体人工步骤、tracker 副作用和 WIP 范围统一按 [ADAPTERS.md](ADAPTERS.md) 适配。阶段执行中途受限时保存已执行内容，继续其他独立工作。
