---
type: project-doc
status: active
date: 2026-11-16
tags: [agents, portability, skills]
---

# 接入与能力降级

本包以普通文件为底座。可以整体复制到项目的 `docs/workflow/personal-coding/`，或放到任意已信任、当前 Agent 可读取的位置。项目契约和任务状态保存在项目内；包的更新由项目显式采用，不靠远端动态注入。

## 最简单的接入

首次对任意 Agent 说：

> 读取 docs/workflow/personal-coding/WORKFLOW.md，按它接续当前开发任务。先复用项目现有规则和验收资产，按需补齐项目契约；已授权的可逆工作连续做完。

能够自动读取仓库规则的工具，可在其**现有、允许编辑**的入口中加入一条带触发条件的相对路径指针：

> 开发新功能、修复、重构或接续任务时，读取 docs/workflow/personal-coding/WORKFLOW.md；首次接入再读同目录 ADAPTERS.md。

指针只是加载入口，不是权限覆盖。入口只读时使用显式指向文档的任务指令，不修改受保护文件。

## 各工具的薄适配

| 工具 | 可选入口 | 需要核实的差异 |
|---|---|---|
| Claude Code | 项目 CLAUDE.md 指针；或整体包置于 `.claude/skills/personal-coding/` | 仅用户可调用的上游 skill 无法假定由模型自动触发；权限、子 Agent 和 hooks 按安装版本配置 |
| Codex | 项目 AGENTS.md 指针；或整体包置于 `.agents/skills/personal-coding/` | skill 自动选择受 `agents/openai.yaml` 的策略影响；工具名、并行和沙箱以当前会话实际能力为准 |
| ZCode | 先显式读文件；已验证的本机 skill 目录可放整体包 | 已知本机存在 `~/.zcode/skills/`；项目级发现路径、自动调用限制、hooks 和循环唤醒仍需实测 |
| 其他 Agent | 显式传入 WORKFLOW.md 路径，按项目契约执行 | 无 shell、浏览器或仓库写权限时只完成可执行部分，清楚报告缺口 |

上表是接入设计，不是三端运行通过声明。跨工具共用的 SKILL.md 只使用 name / description 和相对路径；不写特定工具的 allowed-tools、fork 或模型名。

本机用户级副本由源目录的 `scripts/install.py` 安装；Codex 使用当前文档所列的 `~/.agents/skills/`，不再额外安装第二份同名副本到旧位置。Claude Code 使用 `~/.claude/skills/`；ZCode 使用已观察到的本机 `~/.zcode/skills/`。目录内有文件、客户端发现 skill、模型选择 skill、实际编码闭环通过是四种不同证据，分别验证。

Claude Code skills 位置与调用限制：(source: https://code.claude.com/docs/en/skills)。Codex skills 发现与调用策略：(source: https://learn.chatgpt.com/docs/build-skills)。ZCode 本机事实见调研报告的历史范围与诚实清单，不将其推广为所有版本行为。

## 能力替换

| 所需能力 | 有原生能力时 | 缺失时 |
|---|---|---|
| 专业流程 | 调用当前可用且允许自动调用的 skill | 由核心流程执行；只有需要额外专业知识才读取已信任的相关参考 |
| 独立复核 | 新上下文 reviewer | 做第二遍复核，记录独立性有限；有硬性独立评审要求时保留未满足状态 |
| 并行实现 | 子 Agent + 隔离工作区 + 集成责任方 | 同一依赖图串行执行 |
| 页面操作 | 可用的浏览器驱动 | 优先使用可证明同一行为的接口 / CLI；视觉与浏览器行为仍标为未验证 |
| 远端 tracker | 在已有授权内发布 / 更新 | 保留本地 spec、拆票和待发布内容，继续本地工作 |
| 持续执行 | 已验证的调度器、预算和停止机制 | 有限任务运行并保存接续状态；不宣称无人值守已启用 |

上游标为仅用户调用时，保留其原文件。经适配的本流程自行负责本地规划、拆票和执行；读取资料不构成调用权限或外发权限。上游自带发布、问卷或删除步骤时，先按当前目标和规则调整，不整段无条件执行。

## 首次冒烟

在测试项目中用五类请求验证路由：明确 bug、跨模块功能、UI 方向不清、环境缺 key、请求发布。观察是否分别走短路径、保存完成条件、先查证再问、诚实记录未验、在真实授权边界停下。

三种工具分别记录版本、实际入口、是否自动发现、一次真实产物验证和缺失能力。通过的仅是对应工具 / 版本 / 项目组合；尚未测试的保持“待实测”。
