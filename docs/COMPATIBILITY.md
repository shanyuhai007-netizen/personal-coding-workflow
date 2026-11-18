# 兼容与实测边界

依赖 Python 3.10+、Git 和可读写项目目录。核心流程无需特定框架或运行时；0.3.0包含可选ZCode hook adapter；安装器不会自动启用hooks，也不会修改用户配置。CLI支持已有HEAD的普通Git仓库；submodule另行验收。安装器仅支持单进程操作，恢复覆盖进程中断 / 文件系统调用失败，不承诺断电时的文件系统持久性。

| 环境 | 安装目标 | 证据边界 |
|---|---|---|
| Codex | `~/.agents/skills/personal-coding/` | 本地文件安装可校验；模型按 description 的自动选择由当前客户端决定 |
| Claude Code | `~/.claude/skills/personal-coding/` | 本地文件安装可校验；原生调用及完整任务须在对应版本另测 |
| ZCode | `~/.zcode/skills/personal-coding/` | 来自本机已观察目录；其他版本发现机制须实测 |
| 其他 Agent | 显式读取 WORKFLOW.md | 以会话工具、权限及实际产物证据为准 |

0.3.0确定性测试使用合成Git / 文件案例；ZCode hook runner另有本机隔离试点证据，使用模拟provider与路径shim。它们不能替代真实模型的自然语言路由，也不能外推Claude/Codex桌面原生发现与执行。发布时的实际验证记录以CHANGELOG.md为准，未记录通过的层级保持未验证。

官方机制参考：[Claude Code skills](https://code.claude.com/docs/en/skills)、[Codex skills](https://learn.chatgpt.com/docs/build-skills)。接入时按已装版本核对；目录约定不保证未来版本一致。没有原生 Skill 工具时，按当前环境允许方式读取并执行，记录 `read`。
