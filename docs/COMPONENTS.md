# 来源与依赖

本项目自主维护核心工作流、模板及 Python 工具；无第三方运行时 Python 依赖。未打包第三方 skill 内容或复制受限语料。

## 组件清单

工作流引用的全部组件逐项登记如下；性质为「内部程序」的不依赖外部 skill，按 WORKFLOW 与 [EXECUTION](EXECUTION.md) 对应机制执行，缺组件的加载与降级见 [ROUTING](../ROUTING.md)，上游步骤适配统一见 [ADAPTERS.md](../ADAPTERS.md)。组件均为可选外部依赖，各自许可独立；本仓库不自动下载或覆盖，安装前核查来源、许可与当前客户端支持。

| 组件 | 性质 | 来源 | 引用位置 |
|---|---|---|---|
| grilling、tdd、code-review、diagnosing-bugs、research、retro、handoff、to-spec、to-tickets、implement、implement-spec | 外部 skill | [Matt Pocock skills](https://github.com/mattpocock/skills)；步骤适配 pc-0.2 | clarify / implement / 两轴评审 / research / 阶段边界 / 大任务拆分与实施 |
| modern-web-guidance | 外部 skill | Google Chrome 团队（npm 包 modern-web-guidance，Apache-2.0；源码仓 [GoogleChrome/modern-web-guidance-src](https://github.com/GoogleChrome/modern-web-guidance-src)） | web |
| vercel-react-best-practices | 外部 skill | Vercel（MIT，1.0.0） | react |
| web-design-guidelines | 外部 skill | Vercel（1.0.0） | UI 审计，按需 |
| frontend-design | 外部 skill | Anthropic claude-plugins-official frontend-design 插件 | visual-direction |
| emil-design-eng | 外部 skill | Emil Kowalski 作者官方仓 [emilkowalski/skills](https://github.com/emilkowalski/skills)（MIT）；本机副本为早期快照，落后上游 main | 新 UI 方向打磨，按需 |
| ui-taste-loop | 外部 skill | [自维护外部仓](https://github.com/shanyuhai007-netizen/ui-taste-loop)；适配 pc-visual-1，见 [视觉适配](VISUAL.md)，当前效果仍需真实 UI 票验证 | visual-direction / visual-review |
| fact-review（独立事实核验） | 内部程序 | WORKFLOW「完成条件先于实施」一节 + EXECUTION 独立回执（`--independent`）；不引用外部组件 | fact-review |

来源与许可以 npm registry 元数据及 GitHub 仓库 license 核实（2026-11-19）；登记不以推测填充，发现新的缺口时先标记再补证。

## 设计参考致谢

- [poteto verification-skill-example](https://github.com/poteto/verification-skill-example)：项目级产物验收与 feature map 的设计参考。
- [pstack](https://cursor/plugins/tree/main/pstack)：持续执行和可复核交付的设计参考。
- [Agent Skills specification](https://agentskills.io/specification)：SKILL.md 结构参考。

## 项目级清单

组件清单由每个项目按实际环境生成，记录真实源路径、内容 hash、版本（已知时）、读取 / 原生接口、适配版本。source hash 只锁定捕获的文件；读取其他参考文件时通过 component 的 `--file` 一起封存。不要用一个入口版本号推断全部跨客户端组件相同。
