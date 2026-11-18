# personal-coding-workflow

让编码 Agent 接续任务、选用专业 skill、验证实际产物，并留下可复核证据的个人工作流。中文优先，跨 Codex / Claude Code / ZCode 使用普通 Markdown。本地实验候选版本 **0.3.0**，行为验收尚未完成；含可选任务阶段守卫与ZCode hook适配。ZCode隔离试点使用模拟provider，不证明真实模型路由或恢复能力；hooks需显式配置。

目标是让 Agent 连续完成已授权工作：查证技术事实、复用已有决定和权限，只在缺少必要业务事实、偏好、凭据或授权时请人参与。小改走短路径，跨会话任务才写 spec / 依赖图。

## 安装

需要 Python 3.10+ 和 Git。先克隆并审阅源码：

```sh
git clone https://github.com/shanyuhai007-netizen/personal-coding-workflow.git
cd personal-coding-workflow
python3 scripts/install.py --target codex
python3 scripts/install.py --target codex --check
```

目标可换为 `claude` 或 `zcode`，分别放到 `~/.agents/skills/`、`~/.claude/skills/`、`~/.zcode/skills/` 下的 `personal-coding/`。安装只更新本包，不下载第三方 skill，不改全局入口、hooks 或权限。升级前修改、未托管文件和同版本漂移会被拒绝；升级会保留前一完整目录。中断后重跑，见 [恢复说明](docs/TOOLS.md#安装恢复)。

此 Git 仓库是唯一产品源码；安装目录是锁版本副本，旧文档包是历史基准。更新需审阅新版本、运行测试后重新安装。安装成功、客户端发现、模型实际选择、完整任务通过是四层不同证据。

## 使用

在支持 skill 的客户端显式选择 `personal-coding`，或直接说：

> 读取已安装 personal-coding 的 WORKFLOW.md，按它接续当前任务。沿用项目规则、已有决定和已授权范围，完成验证并记录结果。

首次接入读取 [ADAPTERS.md](ADAPTERS.md)，复用现有项目记录；需要时实例化项目 / 任务 / 发布模板并校对链接。仅用户可调用的外部 skill 按当前环境限制处理。[兼容性](docs/COMPATIBILITY.md) 明确已知边界；没有原生 Skill 工具时可显式读取原文并执行，记录 `read`。

## 工作内容

| 入口 | 用途 |
|---|---|
| [WORKFLOW.md](WORKFLOW.md) | 任务入口、最短路径、完成条件、验证和接续状态 |
| [ROUTING.md](ROUTING.md) | 按阶段加载专业组件，记录真实执行或具体降级理由 |
| [ADAPTERS.md](ADAPTERS.md) | 复用批准、人工步骤适配、真实树评审输入 |
| PROJECT.template.md / TASK.template.md / RELEASE.template.md | 项目契约、任务证据、分通道授权与发布状态 |
| [执行闭环](docs/EXECUTION.md) / [ZCode适配](docs/ZCODE.md) | 从事实生成累计义务，核验阶段推进、输入失效和收口；宿主适配单独启用 |
| [证据工具](docs/TOOLS.md) | WIP 快照、完整检查日志 / 原退出码、组件记录、归档和记录校验 |
| [Benchmark 契约](docs/BENCHMARK.md) | 指标定义、可比环境 / 负载、原始样本与独立复算 |
| [来源与依赖](docs/COMPONENTS.md) | 可选专业 skill 与来源致谢 |

非平凡改动采用覆盖最终树的 Standards / Spec 独立复核。检查日志、组件 hash、真实产物结果和重要样本留到持久位置；必要未验条件不能判完成。push、tracker、代码同步、部署分别记录授权及实际状态，已有明确授权持续沿用。

本包提供流程与辅助工具，不是 Agent runtime 或权限引擎。记录校验只能检查已声明证据的一致性，不能证明模型真实加载、正确思考或保证自动调用。

当前未发布改动将原始验收条件与逐项观测纳入 `finish`；旧实施计划需显式补齐条件，见 [原始条件与逐项观测](docs/EXECUTION.md#原始条件与逐项观测)。源码仍为实验候选，尚未更新安装副本。

## 开发与验证

```sh
python3 -m unittest discover -s tests -v
```

测试使用合成 Git / 文件案例，覆盖真实工作树评审、退出码 / 长日志、证据失效、安装保护与中断恢复。CI 在 Linux / macOS 的 Python 3.10 / 3.13 上运行同一套测试；运行结果以 GitHub Actions 为准。原生三客户端闭环尚需分别验证，见 [版本记录](CHANGELOG.md)。

自有代码与文档采用 [MIT](LICENSE)。第三方 skill 各自许可独立，未随本仓库分发。

## 视觉专项

0.4.0 本地候选将 ui-taste-loop 接入视觉生成/改版阶段：已有方向复用、纯样式独立实现、最终截图独立评审，具体协议见 [VISUAL](docs/VISUAL.md)。上游 skill 单独提供，本包不自动安装；缺必需能力不能报完成。合成路由测试不证明审美效果，首次真实 UI 票仍需验证。
