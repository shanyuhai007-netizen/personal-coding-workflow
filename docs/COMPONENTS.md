# 来源与依赖

本项目自主维护核心工作流、模板及 Python 工具；无第三方运行时 Python 依赖。未打包第三方 skill 内容或复制受限语料。

## 组件清单

工作流引用的全部组件逐项登记如下；性质为「内部程序」的不依赖外部 skill，按 WORKFLOW 与 [EXECUTION](EXECUTION.md) 对应机制执行，缺组件的加载与降级见 [ROUTING](../ROUTING.md)，上游步骤适配统一见 [ADAPTERS.md](../ADAPTERS.md)。组件均为可选外部依赖，各自许可独立；本仓库不自动下载或覆盖，安装前核查来源、许可与当前客户端支持。

| 组件 | 性质 | 来源 | 引用位置 |
|---|---|---|---|
| grilling、tdd、code-review、diagnosing-bugs、research | 外部 skill | [Matt Pocock skills](https://github.com/mattpocock/skills)；步骤适配 pc-0.3 | 计划路径阶段组件：clarify / diagnose（含 protocol）/ research / implement / 两轴评审 |
| retro、handoff、to-spec、to-tickets、implement、implement-spec、triage、wayfinder、grill-with-docs、improve-codebase-architecture | 外部 skill | 同上（上游 `disable-model-invocation: true`）；用户显式调用时按 pc-0.3 适配 | 阶段边界 / 大任务拆分与实施 / issue 分诊与决策地图（[docs/agents](agents/) 配置）——仅用户显式调用，计划路径不产生组件义务 |
| domain-modeling | 外部 skill | 同上（可模型调用）；按 pc-0.3 适配 | 域语言与 ADR（[docs/agents](agents/) 配置，经 grill-with-docs / improve-codebase-architecture 到达）——可模型调用而未接线为阶段组件，无组件义务 |
| modern-web-guidance | 外部 skill | Google Chrome 团队（npm 包 modern-web-guidance，Apache-2.0；源码仓 [GoogleChrome/modern-web-guidance-src](https://github.com/GoogleChrome/modern-web-guidance-src)） | web |
| vercel-react-best-practices | 外部 skill | Vercel（MIT，1.0.0） | react |
| web-design-guidelines | 外部 skill | Vercel（1.0.0） | UI 审计，按需 |
| frontend-design | 外部 skill | Anthropic claude-plugins-official frontend-design 插件 | visual-direction |
| emil-design-eng | 外部 skill | Emil Kowalski 作者官方仓 [emilkowalski/skills](https://github.com/emilkowalski/skills)（MIT）；本机副本为早期快照，落后上游 main | 新 UI 方向打磨，按需 |
| ui-taste-loop | 外部 skill | [自维护外部仓](https://github.com/shanyuhai007-netizen/ui-taste-loop)；适配 pc-visual-1，见 [视觉适配](VISUAL.md)，当前效果仍需真实 UI 票验证 | visual-direction / visual-review |
| web-gui-tester | 外部 skill | ZCode 官方插件市场 zcode-plugins-official browser-use 0.3.0（本机缓存）；方法论跨宿主——原文要求用会话实际提供的浏览器工具运行、工具自身规则优先，本机原文路径 `~/.zcode/cli/plugins/cache/zcode-plugins-official/browser-use/0.3.0/skills/web-gui-tester/SKILL.md`，其他宿主按 read 跨目录复用、不复制版本。步骤适配 pc-0.3 | interaction-verify |
| interrogate | 外部 skill | [pstack](https://github.com/cursor/plugins/tree/main/pstack) `skills/interrogate/SKILL.md`（上游 `disable-model-invocation: true`；许可随上游——pstack 子目录自带 MIT LICENSE，上游仓库 license 字段为 null，2026-11-20 核实）；步骤适配 pc-0.3，见 [ADAPTERS](../ADAPTERS.md#组件步骤适配) | verify（可选义务） |
| 浏览器自动化工具层（control-browser 等） | 宿主工具 | ZCode：browser-use 插件原生（node_repl 驱动，主 agent 专用、子 agent 禁用）；Claude Code：本机 `~/.claude/skills/browser` CDP 脚本包（playwright-mcp 未配置，可选另装）；Codex：未配置，原生能力须实测（2026-11-20 核）。无可用工具时 interaction-verify 记 degraded 并保留手动复验步骤 | interaction-verify 工具层（非流程组件，不单独回执） |
| fact-review（独立事实核验） | 内部程序 | WORKFLOW「完成条件先于实施」一节 + EXECUTION 独立回执（`--independent`）；不引用外部组件 | fact-review |

双模式定性：上游 skill 的可调用性以其 frontmatter 为准（2026-11-20 逐个核对本机 1.3.1 原文）。带 `disable-model-invocation: true` 的 10 个仅在用户显式调用时按 [ADAPTERS](../ADAPTERS.md#组件步骤适配) 适配执行，计划路径（workflow_rules 阶段 components）不为它们产生组件义务——与上游设计一致，非本工作流缺陷。其余 6 个可被模型调用：grilling、tdd、code-review、diagnosing-bugs、research 已接线为阶段组件；domain-modeling 可模型调用而未接线，接线留给实际需要 glossary 义务的后续版本。回执义务集合由阶段 components 代码级锁定，登记在清单与接线进规则是两件事，登记不产生义务。optional_components 接线不改变 frontmatter 触发定性——带 `disable-model-invocation: true` 的组件（如 interrogate）计划路径仍不自动触发，接线只是给用户显式调用的执行一个阶段回执挂载点（可选槽），不执行不产生义务缺口。

来源与许可以 npm registry 元数据及 GitHub 仓库 license 核实（2026-11-19）；登记不以推测填充，发现新的缺口时先标记再补证。

## 设计参考致谢

- [poteto verification-skill-example](https://github.com/poteto/verification-skill-example)：项目级产物验收与 feature map 的设计参考。
- [pstack](https://github.com/cursor/plugins/tree/main/pstack)：持续执行和可复核交付的设计参考；feature map 结构（README 索引 + 四 H2 特性文件）参照其 create-verification-skill 的 feature-map-example。
- [Agent Skills specification](https://agentskills.io/specification)：SKILL.md 结构参考。

## 项目级清单

组件清单由每个项目按实际环境生成，记录真实源路径、内容 hash、版本（已知时）、读取 / 原生接口、适配版本。source hash 只锁定捕获的文件；读取其他参考文件时通过 component 的 `--file` 一起封存。不要用一个入口版本号推断全部跨客户端组件相同。
