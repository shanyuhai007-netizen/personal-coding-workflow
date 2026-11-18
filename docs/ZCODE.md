# ZCode 可选宿主适配

`scripts/zcode_hook.py --record /evidence/task.json --repo /project` 接收ZCode hook stdin。配置限单仓、单任务、单session；仓外不处理。先创建有依据的计划；缺计划时受管Stop也会反馈恢复动作。不要为普通问答启用专用任务hook。

## 配置与验证

检查本机宿主支持的配置与版本，再合并现有用户hooks设置；安装器不启用hooks。下列是可审阅的 `hooks` 配置片段，不是覆盖全局配置的命令：

```json
{
  "hooks": {
    "enabled": true,
    "events": {
      "SessionStart": [{"hooks": [{"type": "process", "command": "python3", "args": ["/skill/scripts/zcode_hook.py", "--record", "/evidence/task.json", "--repo", "/project"]}]}],
      "PostToolUse": [{"hooks": [{"type": "process", "command": "python3", "args": ["/skill/scripts/zcode_hook.py", "--record", "/evidence/task.json", "--repo", "/project"]}]}],
      "PostToolUseFailure": [{"hooks": [{"type": "process", "command": "python3", "args": ["/skill/scripts/zcode_hook.py", "--record", "/evidence/task.json", "--repo", "/project"]}]}],
      "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "process", "command": "python3", "args": ["/skill/scripts/zcode_hook.py", "--record", "/evidence/task.json", "--repo", "/project"]}]}],
      "Stop": [{"hooks": [{"type": "process", "command": "python3", "args": ["/skill/scripts/zcode_hook.py", "--record", "/evidence/task.json", "--repo", "/project"]}]}]
    }
  }
}
```

采用实际绝对路径与可执行Python。新session加载配置；本机帮助、缓存guide、在线文档若有差异，以隔离实测为准。首次SessionStart/工具/Stop事件自动记录到 `<task.json>.events`，task.host只有events_observed表示看到载荷，**不表示所有钩子已启用或原生闭环通过**。

PostToolUse精确匹配注册的Read源路径，并核对工具返回路径、完整内容hash和truncated标记；失败、错路径、内容不符或截断都不能记为成功。非目标同名文件不计。加载事件包含对应就绪阶段的身份，无法归属时stage_id为null，不可用于阶段完成。工具参数/返回结构超出已支持范围时不能假定成功识别。当前自动观察Read；native Skill接口尚未验证，因此启用适配后必须通过Read原文路径完成组件义务；无法产生匹配host事件的方式会保持欠项。ZCode观察已启用后，组件receipt必须引用同任务、同session的宿主事件；手工声明不能替代。

Stop和匹配到的Bash `git commit/push`、`gh pr create/merge`会核验必需项及finish状态；缺项exit2并反馈具体动作。push和PR操作还要求task.external_actions对应通道具备授权记录；仅本地VERIFIED不算外发授权。普通错误不等同成功阻断；应查rejection日志和宿主响应。已通过的任务重验当前输入，恢复后有效收口才放行。外发仍须独立授权，hook放行不授予权限。

## 边界

Stop最多继续3次；达到上限宿主可能正常退出，但任务仍未完成。检查task.status、原始hook日志与完成声明的冲突，不能用CLI exit0判通过。hook被关闭、超时、损坏、其他工具/封装命令、cwd子目录或不同客户端均可能旁路。本适配是合作式可靠性措施，不是不可绕过的权限系统。配置固定的repo必须与payload cwd完全一致；子目录未覆盖。

事件日志包含原始工具载荷与响应，可能有私有内容；保存在仓外，按项目规则处理，不随产品发布。同记录的新session只能在SessionStart以startup/resume事件接续，并将旧session加入绑定历史；其他事件不能抢占绑定。多个并发session会竞争同一记录，最近启动者会接管，故一个task_id应只用于单一活动session。

验证需分开报告：CLI确定性守卫、离线载荷重放、真实宿主自动触发。使用模拟provider及路径隔离的bundled CLI试验，只证明该宿主hook运行路径，不能外推桌面真实模型或其他客户端。必要试点未通过前保持候选，不更新全局安装副本。
