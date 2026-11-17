# 来源与依赖

本项目自主维护核心工作流、模板及 Python 工具；无第三方运行时 Python 依赖。设计参考以下公开的一手资料；未打包第三方 skill 内容或复制受限语料。

- [Matt Pocock skills](https://github.com/mattpocock/skills)：按任务阶段使用 grilling、tdd、code-review 等专业方法。名称与入口可能随上游改变；实际执行以当前安装原文及 hash 为准。
- [poteto verification-skill-example](https://github.com/poteto/verification-skill-example)：项目级产物验收与 feature map 的设计参考。
- [pstack](https://github.com/cursor/plugins/tree/main/pstack)：持续执行和可复核交付的设计参考。
- [Agent Skills specification](https://agentskills.io/specification)：SKILL.md 结构参考。

这些组件均为可选外部依赖，各自许可独立。本仓库不自动下载或覆盖它们；安装缺失组件前核查其来源、许可与当前客户端支持。上游步骤的具体适配统一见 ADAPTERS.md。

组件清单由每个项目按实际环境生成，记录真实源路径、内容 hash、版本（已知时）、读取 / 原生接口、适配版本。source hash 只锁定捕获的文件；读取其他参考文件时通过 component 的 `--file` 一起封存。不要用一个入口版本号推断全部跨客户端组件相同。
