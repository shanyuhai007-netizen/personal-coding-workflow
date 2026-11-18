# 生成清单与推进阶段

这是合作式执行工具：规则负责从已查证事实合成义务，Agent负责提取事实、执行方法和判断内容。CLI通过不证明自然语言选路或执行质量。任务状态留在仓外，安装副本与源码采用同一组规则。

## 建立计划

首次读取 [规则源](../scripts/workflow_rules.json)，将相关事实及依据写入 facts.json。没有提供的可选布尔事实按 false 处理，所以 Agent 必须复核遗漏；goal 是原请求的具体目标。component_sources 是实际可读的规范组件路径，不能指向另一目录中的同名文件。实际文件存在不表示宿主有原生调用能力。接续已有完整实现时明确填 `existing_implementation` 与 `implementation_complete`，计划会核验当前树并跳过implement，只补缺失的验收/评审；事实本身仍需在preflight核验。

```json
{
  "task_id": "cli-empty-input",
  "goal": "空输入返回约定错误而不抛异常",
  "facts": {
    "intent": {"value": "implement", "evidence": "用户请求"},
    "bug": {"value": true, "evidence": "已运行的复现日志"},
    "behavior_change": {"value": true, "evidence": "空输入契约"},
    "nontrivial": {"value": true, "evidence": "影响CLI错误行为"}
  },
  "component_sources": {"tdd": "/skills/tdd/SKILL.md", "diagnosing-bugs": "/skills/diagnosing-bugs/SKILL.md", "code-review": "/skills/code-review/SKILL.md"},
  "max_attempts": 3
}
```

```sh
python3 scripts/evidence.py plan --repo /project --facts /evidence/facts.json --record /evidence/task.json
python3 scripts/evidence.py next /evidence/task.json
python3 scripts/evidence.py next /evidence/task.json --json
```

显示目标、修订号、阶段、所需组件、出口和状态；详细身份留JSON。next选择依赖齐备的首项；必要业务澄清不阻塞独立research。多单元的真实票依赖图留spec，工具不调度独立票组。已有实现仍先核验，适用时用reuse满足对应阶段，不能重新施工。预算耗尽保持受阻，继续其他已就绪项。修复根因并保留证明后，可用 `stage-resume --stage <id> --reason <具体修复> --proof <复验依据>` 开启唯一一次新的有限重试周期；旧失败次数保留在attempt_history。再次耗尽后需新任务及重新审查范围，不可继续清零重试。

## 记录执行与阶段出口

先执行阶段方法并核验产物。组件事件采用JSON：`task_id, stage_id, component, source, mode, status`；status只能成功事件才用success。宿主观察器生成的事件还保存session/tool身份、原始载荷指针。手工整理的read事件必须注明其声明性质，不能称宿主自动观察。native/read事件检查任务、阶段、组件、模式及规范源路径；这些字段仍不是防伪签名。

```sh
python3 scripts/evidence.py component-event /evidence/task.json --stage implement --obligation tdd --mode read --source /skills/tdd/SKILL.md --proof /evidence/red-green.md --status success
python3 scripts/evidence.py stage-receipt /evidence/task.json --stage implement --obligation tdd --mode read --verification pass --source /skills/tdd/SKILL.md --input /project/cli.py --event /evidence/tdd-event.json --artifact /evidence/red-green.md --adaptation pc-0.2 --out /evidence/implement-1.json
python3 scripts/evidence.py stage-complete /evidence/task.json --stage implement --receipt /evidence/implement-1.json
```

每项所需组件先登记事件，再提交一份receipt；无专业组件用 obligation `output`。native只能来自宿主事件；read/reuse手工事件标为agent声明并关联执行核验文件。事件必须登记于当前任务且与任务、阶段、组件、模式、规范源路径/hash相符。ZCode开始观察后，手工事件不能替代宿主事件。证明文件和receipt仍是调用者声明，不能证明思考质量。输入选择与结论有关文件；最终 verify、两轴评审及close自动绑定完整Git树。实现阶段选有关文件，后续无关改动不会让历史事实永久失效。每次next/完成/finish重新核验输入、源、产物、事件hash和前置条件。变化使相关项及依赖返回待验证；旧回执保留。

verify receipt另外必须提供至少一个 `--check /evidence/check/result.json`，来自 [run工具](TOOLS.md#可靠检查)，当前树、原退出码及日志hash均核验。实际产品路径、服务环境和模型质量仍需对应产物，空泛pass声明不能替代它们。独立阶段加 `--independent --reviewer-id <独立上下文ID>`，Standards与Spec必须不同上下文；字段是声明，独立性还须回查原始执行记录。

reuse提供 `--reuse-check <当前适用性核验文件>`；所需组件仍须对应源。degraded、失败、unknown不能满足必需阶段。receipt输出路径不可重用，以便保留返工历史。

## 修订、收口和副作用

范围变化后更新facts，重新plan并提供 `--reason`。阶段义务取并集，修订不能静默删除欠项；原始facts与理由保留。规则hash变化必须显式迁移记录；当前版本不支持自动规则迁移，使用原版本完成旧任务，或另建计划明确核验复用旧成果。

```sh
python3 scripts/evidence.py finish /evidence/task.json
```

仅所有必需项有效时写VERIFIED。未运行finish时，已启用的 [ZCode适配](ZCODE.md) 会在Stop反馈缺项；其他端无此自动保障。外部授权单独记录，不由VERIFIED授予。原始兼容命令validate只校验v0.2记录，不具备义务覆盖或宿主约束，不能代替新计划收口。

真实副作用执行前，先确认授权并将单独授权凭据写入外部动作记录，再用 `operation task.json --stage close --operation-id <稳定操作身份> --result begin` 持久记录unknown。发生回执丢失时先查实际产物和远端操作身份，`--result applied|not_applied --proof <对账文件>`。工具本身不执行副作用；同身份不能再次begin，unknown阻止finish。对账后如需重试，必须确认幂等性/实际未执行，使用可追溯的新操作身份；不能因异常盲重试。

工具不保护恶意改写记录，也不证明所有自然语言技能要求。新增特殊义务需项目契约和适用规则共同复核，规则覆盖之外的硬条件仍保持未满足。
