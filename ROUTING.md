---
type: project-doc
status: active
date: 2026-11-17
tags: [agents, coding, routing]
---

# 专业 skill 路由

选好任务路径后，仅加载当前阶段需要且实际可用的组件。以当前工具列出的 skill 为准；下表名称是候选，不保证所有客户端均已安装。WORKFLOW.md 负责阶段推进，组件不另起一套总流程。

| 触发条件 | 优先组件 | 阶段完成条件 |
|---|---|---|
| 关键业务目标或术语仍有歧义 | grilling / domain-modeling | 影响行为的歧义已解决，决定可追溯 |
| 必须看运行结果才能决定设计 | prototype；有事实缺口时 research | 实验回答具体问题，记录结果及适用限制 |
| 跨会话功能需拆分 | to-spec / to-tickets 的结构 | 完成条件与阻塞边明确；已有 spec / 票直接复用 |
| 实现已明确行为 | tdd；可调用时 implement | 合适的行为测试通过，实际产物符合完成条件 |
| 多票接口清楚、可隔离 | implement-spec 的编排方法 | 按依赖推进，最终集成树复验 |
| 报错、失败、性能回退 | diagnosing-bugs；性能数字另用 benchmark-checklist | 有复现与根因证据，修复后同口径验证 |
| 涉及 HTML / CSS / 客户端 JS | modern-web-guidance | 先核实现代平台用法，再修改 |
| 设计或打磨 UI | frontend-design / emil-design-eng | 遵循项目视觉方向，并运行检查交互 |
| React / Next.js 或 UI 审计 | vercel-react-best-practices / web-design-guidelines | 对应性能、可访问性和交互问题已检查 |
| 无可复跑的产物验收入口 | create-verification-skill 的方法 | 建启动 / doctor / drive / evidence 配方，实际证明一条路径 |
| 宣告完成前 | 项目 verify；prove-it-works / blast-radius 的方法 | 最终版本对应证据，未验范围明确 |
| 非平凡改动待交付 | code-review | Standards / Spec 复核完成，修复后受影响验证已重跑 |
| 重复故障 / 纠正 | retro | 优先落确定性检查或环境修复，记录其效果 |
| 跨 Agent 且现有任务状态不足 | handoff | 下一 Agent 可定位代码、未完成项和下一动作 |

调用前检查实际可调用性、已有授权及副作用。标为仅用户调用的组件不尝试原生自动调用；由本流程执行自己的相应步骤，或在工具和规则允许时读取已信任的过程参考。发布、删除、环境变更仍单独遵守当前权限。

没有某个 skill 时，继续执行核心流程能覆盖的部分。必要能力缺失时标出缺口，继续其他独立工作；不把“没装 skill”自动变成让用户决策的理由。
