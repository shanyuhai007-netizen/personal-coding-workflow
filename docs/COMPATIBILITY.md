# 兼容与实测边界

依赖 Python 3.10+、Git 和可读写项目目录。核心流程无需特定框架或运行时；本包没有调度器、自动唤醒、hooks 或权限引擎。CLI 支持已有 HEAD 的普通 Git 仓库；submodule 另行验收。安装器仅支持单进程操作，恢复覆盖进程中断 / 文件系统调用失败，不承诺断电时的文件系统持久性。

| 环境 | 安装目标 | 证据边界 |
|---|---|---|
| Codex | `~/.agents/skills/personal-coding/` | 本地文件安装可校验；模型按 description 的自动选择由当前客户端决定 |
| Claude Code | `~/.claude/skills/personal-coding/` | 本地文件安装可校验；原生调用及完整任务须在对应版本另测 |
| ZCode | `~/.zcode/skills/personal-coding/` | 来自本机已观察目录；其他版本发现机制须实测 |
| 其他 Agent | 显式读取 WORKFLOW.md | 以会话工具、权限及实际产物证据为准 |

本版确定性测试使用合成 Git / 文件案例；新上下文测试使用隔离小任务。它们不能替代三个客户端各自的原生发现、自动路由与真实编码闭环。发布时的实际验证记录以 CHANGELOG.md 为准，未记录通过的层级保持未验证。

官方机制参考：[Claude Code skills](https://code.claude.com/docs/en/skills)、[Codex skills](https://developers.openai.com/codex/skills/)。接入时按已装版本核对；目录约定不保证未来版本一致。没有原生 Skill 工具时，按当前环境允许方式读取并执行，记录 `read`。
