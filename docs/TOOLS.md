# 本地证据工具

新的任务闭环使用 [计划/阶段/收口](EXECUTION.md)；可选自动观察见 [ZCode适配](ZCODE.md)。下文validate保留旧记录兼容，只检查声明，不校验任务预期义务集合。

从源仓库或已安装 skill 目录运行 `python3 scripts/evidence.py --help`。仅依赖 Python 3.10+ / Git；目标项目需已有 HEAD。工具产生的记录与日志留本地，不自动发布。

## 完整工作树评审

```sh
python3 scripts/evidence.py snapshot --repo /path/to/project --base HEAD --out /path/to/evidence/review-1
```

base 是任务起点或明确集成基线；不总是 HEAD。输出目录必须在目标仓外且尚不存在，避免把证据本身递归加入快照。输出 `review.patch` 和 `snapshot.json`（base、head、tree、patch hash、精确 diff 命令）。快照使用备用 index，保留真实 HEAD / index；包含 staged、unstaged、删除、非忽略 untracked 以及强制暂存的忽略文件。

交给 reviewer `snapshot.json` 中的 `git diff BASE TREE`，不能替换成 `base...HEAD`。读取 patch 前核对 hash；在证据仍需 Git tree 对象时保留仓库，重要 diff 也有持久 patch 副本。暂停并行写入后固定快照，Git filter / submodule / 特殊 index 标记需额外核查。

## 可靠检查

```sh
python3 scripts/evidence.py run --repo /path/to/project --out /path/to/evidence/check-1 -- python3 -m unittest discover -s tests -v
```

输出 `output.log`（完整 stdout / stderr 合并）与 `result.json`（原始 argv、cwd、HEAD、前后树、exit_code、持续时间、日志 hash）。包装器返回原命令状态；信号以 128+信号号返回，原负值保留在 JSON。命令无法启动时记录 127。输出写文件，不在终端实时回显；查看完整日志判断实际通过数。

默认不经 shell；需要管道时显式传 `bash -o pipefail -c 'your-check | tee your-log'`。包装器无法挽回命令内部自行丢掉的状态或输出。命令修改代码树时前后 hash 不同，需完成修改后重跑；构建产物按项目约定忽略。被硬杀 / 机器崩溃导致没有 result.json 时，该次检查保持未完成。

## 组件执行记录

先实际加载组件原文、按 ADAPTERS.md 执行并保存调用 trace / 决策 / 测试 / 评审结果，再封存：

```sh
python3 scripts/evidence.py component --name tdd --mode read --skill /path/to/tdd/SKILL.md --file /path/to/tdd/tests.md --proof /path/to/execution.md --adaptation pc-0.3 --out /path/to/evidence/tdd-1
```

`native`、`read`、`reuse`、`degraded` 定义见 ROUTING.md。degraded 可省 skill，但必须加 `--reason` 写观察到的缺失 / 限制。proof 必须是非空的真实执行证据或复用核查，不能只有文件名清单。输出 `component.json`、源文件副本及执行证据副本；记录原始路径与 hash，便于跨客户端定位同名差异。

这些文件是调用方声明，工具只捕获字节和字段，不证明加载、原生调用成功或执行质量。审阅实际 trace / 输出才能判断；遗漏触发组件也无法仅靠脚本发现。

## 持久归档

```sh
python3 scripts/evidence.py archive --file /path/to/driver.py --file /path/to/samples.tsv --file /path/to/environment.md --out /path/to/durable/benchmark-1
python3 scripts/evidence.py verify-archive /path/to/durable/benchmark-1
```

逐个选脱敏文件，名称须唯一。输出 manifest.json 和副本；先验证副本与任务指针，再清理临时源。archive 不自动脱敏、不递归搬整个会话；目录类型自行选文件。改变归档内容后 hash 校验失败。证据是否适合入 git 由项目数据约束决定。

## 非平凡任务的完成记录校验

小改可继续使用简短 Markdown，不必填全套 JSON。非平凡任务在外部证据目录写 `task.json`，相对路径以该文件目录为基准：

```json
{
  "tree": "填 snapshot.json 的最终 tree",
  "independent_required": true,
  "conditions": [
    {"id": "observable-behavior", "required": true, "status": "pass",
     "evidence": {"path": "behavior.md", "sha256": "填实际 hash"}}
  ],
  "checks": ["check-1/result.json"],
  "components": ["tdd-1/component.json"],
  "reviews": [
    {"axis": "standards", "tree": "同一最终 tree", "status": "pass", "independent": true,
     "evidence": {"path": "standards.md", "sha256": "填实际 hash"}},
    {"axis": "spec", "tree": "同一最终 tree", "status": "pass", "independent": true,
     "evidence": {"path": "spec.md", "sha256": "填实际 hash"}}
  ]
}
```

```sh
python3 scripts/evidence.py validate /path/to/evidence/task.json --repo /path/to/project
```

校验当前树、必需条件通过及证据 hash、检查状态 / 前后树 / 日志 hash、组件模式 / 源副本 / 执行证据、两轴评审与独立性。缺失、过期、失败或格式错误返回非零。输出 `RECORD_VALID` 只表示声明的记录符合结构与一致性要求；条件是否完整、证据是否真实、语义与品味仍需 Agent 判断。

`independent_required` 默认 true；项目允许受限自查时须填写非空 `independence_reason` 后显式设 false，交付仍注明受限。硬性独立要求不因缺能力而取消。外部服务、忽略配置或模型版本变化不会自动反映在 Git tree，需人工记录环境身份并使受影响证据失效。JSON 记录迁移位置时更新路径并重验。

## 安装恢复

`install.py` 只在源仓库运行，按 `scripts/install.py` 中的 `FILES` 白名单分发工作流规则、CLI、可选ZCode adapter和文档；不自动安装专业组件或启用hooks。升级采用完整staging、事务日志和目录切换；被替换旧版备份到客户端技能扫描路径之外的状态目录 `~/.local/state/personal-coding/backups/<宿主>/<技能名>/<版本>/`（可用 `PERSONAL_CODING_STATE_ROOT` 重定向），每目录仅保留最近一份，更旧版本从 git 历史找回。两个rename之间可能短暂没有目标目录，客户端应在升级结束后重新加载。

安装中断后直接重跑原安装命令，先恢复旧目录或采用已经切换好的完整目录，再验证本地改动。`--check` 始终只读，遇未完成事务报错。恢复后的用户改动仍拒绝覆盖；先备份、比较并显式迁移。stage 残留供检查与回退，工具不自动删掉用户资料；恢复逻辑同时接受旧版日志中的同级 `.previous-` 备份名与新版状态目录绝对路径。回退时用已知旧版本源重新安装，被替换目录正常转入状态目录备份。并发安装不支持；不要在客户端同时写安装目录时升级。恢复面向进程中断，不保证断电场景。
