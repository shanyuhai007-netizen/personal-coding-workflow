# 生成清单与推进阶段

这是合作式执行工具：规则负责从已查证事实合成义务，Agent负责提取事实、执行方法和判断内容。CLI通过不证明自然语言选路或执行质量。任务状态留在仓外，安装副本与源码采用同一组规则。

## 建立计划

首次读取 [规则源](../scripts/workflow_rules.json)，将相关事实及依据写入 facts.json。台账面向 WORKFLOW.md 全路径任务；满足其小改硬判据的轻量任务不建 facts、计划与回执，保留检查日志和验证性本地提交即可，判据失守再进入本节流程。没有提供的可选布尔事实按 false 处理，所以 Agent 必须复核遗漏；goal 是原请求的具体目标。component_sources 是实际可读的规范组件路径，不能指向另一目录中的同名文件。实际文件存在不表示宿主有原生调用能力。接续已有完整实现时明确填 `existing_implementation` 与 `implementation_complete`，计划会核验当前树并跳过implement，只补缺失的验收/评审；事实本身仍需在preflight核验。

```json
{
  "task_id": "cli-empty-input",
  "goal": "空输入返回约定错误而不抛异常",
  "conditions": [
    {"id": "empty-input", "source": "/project/docs/SPEC.md", "locator": "CLI / 空输入",
     "requirement": "空输入返回约定错误而不抛异常", "target": "local CLI fixture"}
  ],
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

台账与证据目录放在仓外的持久位置：系统临时目录（/tmp、$TMPDIR 等）会被定期清理，`plan` 与 `finish` 拒绝此类路径；项目同级 `.personal-coding-evidence/` 或 `~/.local/state/personal-coding/<repo>/<task>/` 是可用约定。合成测试以 `PERSONAL_CODING_ALLOW_VOLATILE_RECORD=1` 显式豁免。

## 记录执行与阶段出口

先执行阶段方法并核验产物。组件事件采用JSON：`task_id, stage_id, component, source, mode, status`；status只能成功事件才用success。宿主观察器生成的事件还保存session/tool身份、原始载荷指针。手工整理的read事件必须注明其声明性质，不能称宿主自动观察。native/read事件检查任务、阶段、组件、模式及规范源路径；这些字段仍不是防伪签名。

```sh
python3 scripts/evidence.py component-event /evidence/task.json --stage implement --obligation tdd --mode read --source /skills/tdd/SKILL.md --proof /evidence/red-green.md --status success
python3 scripts/evidence.py stage-receipt /evidence/task.json --stage implement --obligation tdd --mode read --verification pass --source /skills/tdd/SKILL.md --input /project/cli.py --event /evidence/tdd-event.json --artifact /evidence/red-green.md --adaptation pc-0.2 --out /evidence/implement-1.json
python3 scripts/evidence.py stage-complete /evidence/task.json --stage implement --receipt /evidence/implement-1.json
```

每项所需组件先登记事件，再提交一份receipt；无专业组件用 obligation `output`，此时不需要事件文件。`--event` 可省略：省略时组件义务自动选用本任务最新登记的同阶段、同组件、同 mode 成功事件；显式传入时必须是 component-event 产出的 JSON。native只能来自宿主事件；read/reuse手工事件标为agent声明并关联执行核验文件。事件必须登记于当前任务且与任务、阶段、组件、模式、规范源路径/hash相符。ZCode开始观察后，手工事件不能替代宿主事件。证明文件和receipt仍是调用者声明，不能证明思考质量。输入选择与结论有关文件；最终 verify、两轴评审及close自动绑定完整Git树。实现阶段选有关文件，后续无关改动不会让历史事实永久失效。早期组件回执（diagnose/web/react 等）按当时相关文件绑定：实现落地改变相关文件后回折待验证，实现后预期重开一次（2026-11-18 三任务均如此，约 15 分钟/次的已知成本，排期按此计）。每次next/完成/finish重新核验输入、源、产物、事件hash和前置条件。变化使相关项及依赖返回待验证；旧回执保留。

verify receipt另外必须提供至少一个 `--check /evidence/check/result.json`，来自 [run工具](TOOLS.md#可靠检查)，当前树、原退出码及日志hash均核验。实际产品路径、服务环境和模型质量仍需对应产物，空泛pass声明不能替代它们。独立阶段加 `--independent --reviewer-id <独立上下文ID>`，Standards与Spec必须不同上下文；字段是声明，独立性还须回查原始执行记录。

reuse提供 `--reuse-check <当前适用性核验文件>`；所需组件仍须对应源。degraded、失败、unknown不能满足必需阶段。receipt输出路径不可重用，以便保留返工历史。

## 修订、收口和副作用

范围变化后更新facts，重新plan并提供 `--reason`。阶段义务取并集，修订不能静默删除欠项；原始facts与理由保留。规则hash变化必须显式迁移记录；当前版本不支持自动规则迁移，使用原版本完成旧任务，或另建计划明确核验复用旧成果。

```sh
python3 scripts/evidence.py finish /evidence/task.json
```

仅所有必需阶段及下节原始条件的有效观测齐备时写VERIFIED。未运行finish时，已启用的 [ZCode适配](ZCODE.md) 会在Stop反馈缺项；其他端无此自动保障。外部授权单独记录，不由VERIFIED授予。原始兼容命令validate只校验v0.2记录，不具备义务覆盖或宿主约束，不能代替新计划收口。

## 原始条件与逐项观测

`conditions` 是项目既有验收入口的引用投影，每项必需：稳定 `id`、可读本地 `source`、原文位置 `locator`、条件原文 `requirement`、约定实例/环境 `target`。远端条件先保存允许本地留存的原文快照，注明 URL/版本。source 相对 facts.json 解析；工具保存其 hash，不解析自然语言。覆盖是否完整、投影是否忠实由 preflight 及独立评审核对，不能靠改 target 或用替身放宽原条件。纯问答不要求 conditions；旧实施计划需显式 replan 补齐。

实际验收后复用既有日志/产物，写 JSON 观测列表。`pass/fail` 需要实际触发的 `behavior`、与原条件一致的 `target`、具体 `observation` 及非空原始 `evidence` 文件路径列表；`fail/unknown` 另写具体 `next_action`。`unknown` 未执行时可只写下一动作，已尝试时保留观察及原始证据；报告中提供的这些字段也会保存和展示。证据路径相对报告文件解析。每次报告使用新文件保留旧原文。

```json
[
  {"id": "empty-input", "status": "pass", "behavior": "在 CLI 输入空字符串",
   "target": "local CLI fixture", "observation": "返回约定错误，进程未抛异常",
   "evidence": ["empty-input.log"]}
]
```

```sh
python3 scripts/evidence.py acceptance /evidence/task.json --report /evidence/observations-1.json
python3 scripts/evidence.py finish /evidence/task.json
```

acceptance 只登记观测及当前完整树，不授予完成；缺项可先登记，finish 逐项拒绝缺失、失败或未知条件。工具自动保存报告/证据 hash、原条件及树身份；原文、证据或代码变化使旧观测失效。修订条件必须 replan 并写具体 reason，历史保留前后投影；同标签改写也需重新核验。观测变化会让两轴评审和 close 待验证，最终报告在评审前固定，返工后更新并复审。

收口直接展示每项条件、行为、目标版本/实例/环境、观察、证据及剩余动作。树身份只能证明对应的本地代码；部署版本、真实服务实例和样本范围由原始证据及 reviewer 核对。只要求本地修复时 target 使用约定本地实例；生产发布状态单列。原请求要求生产故障消失时保留该条件，未复验不能以本地测试替代。

评审材料按 [评审输入](../ADAPTERS.md#评审输入) 提供相关原始证据。结构与 hash 校验不证明观察真实或结论足够，检查日志全绿也不能独自证明全部原始目标达成。

## 副作用对账

真实副作用执行前，先确认授权并将单独授权凭据写入外部动作记录，再用 `operation task.json --stage close --operation-id <稳定操作身份> --result begin` 持久记录unknown。发生回执丢失时先查实际产物和远端操作身份，`--result applied|not_applied --proof <对账文件>`。工具本身不执行副作用；同身份不能再次begin，unknown阻止finish。对账后如需重试，必须确认幂等性/实际未执行，使用可追溯的新操作身份；不能因异常盲重试。

工具不保护恶意改写记录，也不证明所有自然语言技能要求。新增特殊义务需项目契约和适用规则共同复核，规则覆盖之外的硬条件仍保持未满足。

前端事实提取必须显式核对 ui / visual_change。视觉专项组件来源、预算、复用和最终树证据按 [视觉适配](VISUAL.md)；未提供事实不代表已经检查不适用。
