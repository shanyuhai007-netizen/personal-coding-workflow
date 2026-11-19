---
name: personal-coding
description: 在开发项目中推进新功能、修复、重构或接续已有任务，按项目契约自动选择流程、验证产物并维护交接状态。用于执行编码任务；纯问答和一般资料整理无需启用。
---

读取 [WORKFLOW.md](WORKFLOW.md)，按其中的入口判断推进当前任务。

执行任务先按 [执行说明](docs/EXECUTION.md) 从有依据的事实生成或恢复计划，向用户显示当前阶段和通过依据；每个就绪阶段执行组件、核验产物、记录并推进，最后运行finish。普通问答直接回答。

选定路径后按 [ROUTING.md](ROUTING.md) 加载、执行适用的专业组件，记录模式 / 来源 hash / 适配与产出；当前阶段完成后自动推进下一阶段，直到任务完成或遇到必要阻塞。提问前先检查能否查证、实验、复用既有决定，或在已授权范围内自主决定。

接入新项目或当前工具缺少能力时，读取 [ADAPTERS.md](ADAPTERS.md)；组件的性质与来源以 [COMPONENTS](docs/COMPONENTS.md) 清单为准。项目契约与任务记录分别使用 [PROJECT.template.md](PROJECT.template.md)、[TASK.template.md](TASK.template.md) 的结构，并优先沿用项目已有等价文件。

本入口不授予外发、生产操作或额外工具权限。缺少组件时先记录具体查找或限制证据，再按 ADAPTERS.md 降级；必要未验条件保留未满足状态。
