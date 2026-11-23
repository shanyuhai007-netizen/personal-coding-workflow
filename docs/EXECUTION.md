# 生成清单与推进阶段

这是合作式执行工具：规则负责从已查证事实合成义务，Agent负责提取事实、执行方法和判断内容。CLI通过不证明自然语言选路或执行质量。任务状态留在仓外，安装副本与源码采用同一组规则。

## 建立计划

首次读取 [规则源](../scripts/workflow_rules.json)，将相关事实及依据写入 facts.json。台账面向 WORKFLOW.md 全路径任务；满足其小改硬判据的轻量任务不建 facts、计划与回执，保留检查日志和验证性本地提交即可，判据失守再进入本节流程。没有提供的可选布尔事实按 false 处理，所以 Agent 必须复核遗漏；goal 是原请求的具体目标。 推翻、替换或实质改写既有 ADR 或设计契约时填 `formal_decision=true`，即使任务入口是 bug 修复。以旧 ADR 和复现证据为依据，在写新 ADR 或实现前完成计划生成的 `fact-review`。修补 ADR 错字、链接或忠实执行已批准决定沿用原事实。实施中才发现设计反转时先 replan，再继续该阶段。component_sources 是实际可读的规范组件路径，不能指向另一目录中的同名文件。实际文件存在不表示宿主有原生调用能力。接续已有完整实现时明确填 `existing_implementation` 与 `implementation_complete`，计划会核验当前树并跳过implement，只补缺失的验收/评审；事实本身仍需在preflight核验。

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

多票批量（一次会话收尾多张独立票，如「做完当前 open issues」）不按票各建台账，用单份 facts 承载整批：goal 写明批次范围，conditions 按票前缀分组（如 `56-1`、`47-2`），source 各指向对应原票条件的本地快照；异构票（修复 / 调查 / 功能混批）facts 取并集并在 evidence 注明混合依据，观测逐条件归位，finish 按全部条件收口。计划落成即按 [CONTEXT.md](CONTEXT.md) 多票默认编排执行——已批票多于一张时逐票实施子上下文、worktree 隔离、共享 seam 的票按依赖串行。会话以 handoff 文件接手多票收尾时入口相同：按 handoff 内票清单生成上述单份批次 facts，plan 后进 CONTEXT.md 默认编排；handoff 是接续载体不是免账凭证，缺的事实先补查再入账。批量入口缺这一形状时，会话容易整体绕开台账另做手工收口（2026-11-22 实测：4 票收尾会话未建账，证据散落无状态机）；不要因票多而弃账，形状不合适就修订 facts 而不是绕开。

台账与证据目录放在仓外的持久位置：系统临时目录（/tmp、$TMPDIR 等）会被定期清理，`plan` 与 `finish` 拒绝此类路径；项目同级 `.personal-coding-evidence/` 或 `~/.local/state/personal-coding/<repo>/<task>/` 是可用约定。合成测试以 `PERSONAL_CODING_ALLOW_VOLATILE_RECORD=1` 显式豁免。

## 记录执行与阶段出口

阶段就绪时先读取完整组件原文或从宿主原生调用，立即保留加载记录。执行阶段后保存实际产物并登记回执。组件事件采用JSON：`task_id, stage_id, component, source, mode, status`；status只能成功事件才用success。宿主观察器生成的事件还保存session/tool身份、原始载荷指针。手工整理的read事件必须注明其声明性质，不能称宿主自动观察。native/read事件检查任务、阶段、组件、模式及规范源路径；这些字段仍不是防伪签名。

```sh
python3 scripts/evidence.py component-event /evidence/task.json --stage implement --obligation tdd --mode read --source /skills/tdd/SKILL.md --proof /evidence/red-green.md --status success
python3 scripts/evidence.py stage-receipt /evidence/task.json --stage implement --obligation tdd --mode read --verification pass --source /skills/tdd/SKILL.md --input /project/cli.py --event /evidence/tdd-event.json --artifact /evidence/red-green.md --adaptation pc-0.3 --out /evidence/implement-1.json
python3 scripts/evidence.py stage-complete /evidence/task.json --stage implement --receipt /evidence/implement-1.json
```

每项所需组件先登记事件，再提交一份receipt；无专业组件用 obligation `output`，此时不需要事件文件。`--event` 可省略：省略时组件义务自动选用本任务最新登记的同阶段、同组件、同 mode 成功事件；显式传入时必须是 component-event 产出的 JSON。native只能来自宿主事件；read/reuse手工事件标为agent声明并关联执行核验文件。事件必须登记于当前任务且与任务、阶段、组件、模式、规范源路径/hash相符。ZCode开始观察后，手工事件不能替代宿主事件。证明文件和receipt仍是调用者声明，不能证明思考质量。输入选择与结论有关文件；最终 verify、两轴评审及close自动绑定完整Git树。实现阶段选有关文件，后续无关改动不会让历史事实永久失效。

早期组件回执（diagnose/web/react 等）按当时相关文件绑定，预期修改不应设计成回折，两条低成本路径：

- **预定修改对象在回执落成时封存**：`stage-receipt --pin-input <path>` 把该输入的字节副本存入 `<回执名>.inputs/`，身份绑定快照而非活文件。任务随后按计划修改该文件不再使回执待验证；快照被改动即失效。tree 绑定阶段（verify、两轴评审、close 等）不接受 pin——最终证据仍须对应最终交付树。
- **语义未变仅 hash 变化时重录**：`receipt-refile --receipt <旧回执> --stage <id> --reason <语义未变的依据> --out <新回执>` 以当前 hash 重发。工具逐字复制其余字段、封存源回执 hash、记录变更路径，agent 只确认语义。仅 file 绑定回执可 refile；tree/条件绑定的失效必须重做对应工作。同一文件不能同时作为 `--input` 与 `--pin-input`。

每次next/完成/finish重新核验输入、源、产物、事件hash和前置条件。变化使相关项及依赖返回待验证；仅因依赖回折的阶段在依赖恢复且回执仍可验证时自动回升通过（降级与回升均记入台账 `invalidation_history`/`revalidations`），计划修订显式要求的 preflight 重核（`recheck_required`）不被自动回升替代，需重新 stage-complete 才清除。旧回执保留。

verify receipt另外必须提供至少一个 `--check /evidence/check/result.json`，来自 [run工具](TOOLS.md#可靠检查)，当前树、原退出码及日志hash均核验。interaction-verify 回执另须 `--doctor-check <run result.json>` 提供捕获的 doctor 检查（消费项目契约 Doctor 字段，证明运行实例为当前工作区/代码/端口/隔离数据集），校验口径与 verify 检查相同；契约缺 Doctor 字段时按缺组件降级，交互条件保持未验。doctor 失败进入阶段预算与 stage-resume 单周期封顶，不无限重试。实际产品路径、服务环境和模型质量仍需对应产物，空泛pass声明不能替代它们。独立阶段加 `--independent --reviewer-id <独立上下文ID>`，Standards与Spec必须不同上下文；字段是声明，独立性还须回查原始执行记录。

reuse提供 `--reuse-check <当前适用性核验文件>`；所需组件仍须对应源。degraded、失败、unknown不能满足必需阶段。receipt输出路径不可重用，以便保留返工历史。

阶段成本：`stage-complete --cost <json文件>` 可附调用者声明的该阶段成本——`tokens`/`duration_ms` 非负数、`basis` 必填（说明计量来源，如宿主 subagent 计量或会话读数），存入阶段 `costs` 并与完成时间戳一起保留历史；回执落成另记 `at` 时间戳。两者使下轮可按阶段分解墙钟与 token。声明不是工具观测，口径以 basis 自述为准，评审可核对。

close 阶段按来源分别记录 `last_request`、`main_total`、`child_total`，每项采用 `{"tokens": 数量, "basis": "来源、会话或回合范围、是否含缓存输入"}`。末值反映末次请求大小，主会话累计对任务覆盖的逐请求用量求和。子上下文返回时先保存该回合用量和原始记录指针，再发送继续消息，防止宿主覆盖 transcript。缺数据的口径在收口写 unavailable；已有 `tokens` 仍可用于单阶段计量，混合总数不能补齐缺项。

## 修订、收口和副作用

范围变化后更新facts，重新plan并提供 `--reason`。阶段义务取并集，修订不能静默删除欠项；原始facts与理由保留。规则hash变化必须显式迁移记录；当前版本不支持自动规则迁移，使用原版本完成旧任务，或另建计划明确核验复用旧成果。

```sh
python3 scripts/evidence.py finish /evidence/task.json
```

仅所有必需阶段及下节原始条件的有效观测齐备时写VERIFIED。 交付前按 [WORKFLOW §5](../WORKFLOW.md#5-验证评审与修复) 重读并核对最终树。启用 ZCode 适配时，交付命令另核验 finish 后同会话对已安装 WORKFLOW.md 的完整读取。未运行finish时，已启用的 [ZCode适配](ZCODE.md) 会在Stop反馈缺项；其他端无此自动保障。外部授权单独记录，不由VERIFIED授予。原始兼容命令validate只校验v0.2记录，不具备义务覆盖或宿主约束，不能代替新计划收口。

## 原始条件与逐项观测

`conditions` 是项目既有验收入口的引用投影，每项必需：稳定 `id`、可读本地 `source`、原文位置 `locator`、条件原文 `requirement`、约定实例/环境 `target`。远端条件先保存允许本地留存的原文快照，注明 URL/版本。source 相对 facts.json 解析；工具保存其 hash，不解析自然语言。覆盖是否完整、投影是否忠实由 preflight 及独立评审核对，不能靠改 target 或用替身放宽原条件。纯问答不要求 conditions；旧实施计划需显式 replan 补齐。

实际验收后复用既有日志/产物，写 JSON 观测列表。`pass/fail` 需要实际触发的 `behavior`、与原条件一致的 `target`、具体 `observation` 及非空原始 `evidence` 文件路径列表；`fail/unknown` 另写具体 `next_action`。`unknown` 未执行时可只写下一动作，已尝试时保留观察及原始证据；报告中提供的这些字段也会保存和展示。证据路径相对报告文件解析。每次报告使用新文件保留旧原文。

```json
[
  {"id": "empty-input", "status": "pass", "behavior": "在 CLI 输入空字符串",
   "target": "local CLI fixture", "observation": "返回约定错误，进程未抛异常",
   "evidence": ["empty-input.log"],
   "numbers": [
     {"claim": 21, "kind": "exact", "source": "empty-input.log", "pattern": "\\bok\\b", "compute": "count"},
     {"claim": 95.2, "kind": "approx", "tolerance": 0.5, "source": "empty-input.log",
      "numerator": "\\bok\\b", "denominator": "\\b(ok|FAIL|ERROR)\\b", "compute": "ratio", "scale": 100}
   ]}
]
```

观测引用的关键数字（测试计数、比例、中位数等交付物会转述的量）用 `numbers` 声明做机械重算：每项绑定封存源文件（通常是 [run工具](TOOLS.md#可靠检查) 的 output.log；路径相对报告解析，保存 hash）、提取正则（Python `re`，有捕获组时取第一组）与重算方式——`count`/`sum`/`mean`/`median`/`min`/`max` 对提取值计算，`ratio` 用 `numerator`+`denominator` 两个计数模式相除（可选 `scale`，如百分比 ×100）。两级判据防误报：`exact`（默认）按声明位数四舍五入后必须与重算值一致；`approx` 必须给出非负 `tolerance` 且重算值落在容差内。重算失败的观测降级为 `unknown`（对应条件回到未验），不新增硬阶段；源文件事后变化由 hash 校验拦截。声明由调用者撰写，工具只保证「该数字可从该封存样本重算」，单位、分桶与口径仍是评审义务。

```sh
python3 scripts/evidence.py acceptance /evidence/task.json --report /evidence/observations-1.json
python3 scripts/evidence.py finish /evidence/task.json
```

acceptance 只登记观测及当前完整树，不授予完成；缺项可先登记，finish 逐项拒绝缺失、失败或未知条件。工具自动保存报告/证据 hash、原条件及树身份；原文、证据或代码变化使旧观测失效。修订条件必须 replan 并写具体 reason，历史保留前后投影；同标签改写也需重新核验。观测变化会让两轴评审和 close 待验证，最终报告在评审前固定，返工后更新并复审。

收口直接展示每项条件、行为、目标版本/实例/环境、观察、证据及剩余动作。 通过数从对应日志提取，归属以 `run` 的 `tree_before` / `tree_after` 为准。两者均与交付树一致时才列为终树检查。多票批量下每票的 run 检查以其自身 worktree 的 `tree_before` / `tree_after` 归属，评审树＝检查树＝该票提交树，票间无需 stash 互让。文件数从最终评审快照对应的 base→tree Git 差异重算，采用相同重命名口径。树身份只能证明对应的本地代码；部署版本、真实服务实例和样本范围由原始证据及 reviewer 核对。只要求本地修复时 target 使用约定本地实例；生产发布状态单列。原请求要求生产故障消失时保留该条件，未复验不能以本地测试替代。

评审材料按 [评审输入](../ADAPTERS.md#评审输入) 提供相关原始证据。登记各就绪评审轴的组件加载后，运行 `review-input <task.json> --stage standards|spec-review`，把返回的 JSON 连同实际验收报告、日志与快照交给 reviewer。由 reviewer 输出 JSON，含原样的 `reviewed` 对象、该独立上下文的 `reviewer_id`、`verdict` 和非空 `assessment`，说明所核验的原始证据及结论。归档原始输出，`stage-receipt --review <reviewer.json>` 用其绑定当前验收、条件及树。相同代码树上的验收变化由原 reviewer 核对增量并出新报告。原 reviewer 无法继续时，另请独立 reviewer 对完整材料重审，在报告中写 `"scope": "full"` 和具体 `replacement_reason`。保留初评及增量原文。从早期版本接续时，缺独立报告绑定的两轴回执需补做复核。结构与 hash 校验不证明观察真实或结论足够，检查日志全绿也不能独自证明全部原始目标达成。

## 副作用对账

检查项目的 [发布授权表](../RELEASE.template.md) 与宿主权限。本地 commit 遵循已授权工作及仓库规则。Issue 的建、评、关各自沿用覆盖目标仓库和内容的现有授权，与 push 分开处理。push、部署与公开外发各自按适用的显式授权执行。远程删除、清理类操作（删远端分支、清理云资源 / 环境、撤销已发布物）同入显式授权档；执行中发现待清理资源先记为观察项，不未经授权顺手删除。授权缺失只挂起对应动作，其余动作按各自授权继续。授权依据留在动作记录，用户规则和发布限制优先。

对可能发生回执丢失的动作，执行前用 `operation task.json --stage close --operation-id <稳定操作身份> --result begin` 持久记录 unknown。查到实际产物后，提交 `--result applied|not_applied --proof <对账文件>`；unknown 阻止 finish，重复 begin 被拒。需要重试时先确认未应用和幂等性，再使用可追溯的新操作身份。已执行且没有 begin 记录的动作（如收口后的本地提交或后续会话已完成的跟踪动作），可凭提交对象、工单快照等持久证据用 `--result applied --late --proof <凭据>` 补录。补录保留登记时间和已有 VERIFIED，命令仅记账。

[ZCode 受管交付命令](ZCODE.md#配置与验证) 先完成 finish 与交付读取，再执行已授权动作。宿主已在执行前保存原始命令事件；确认实际结果后凭证补录。若结果不明，检查提交对象或远端实际状态，仍无法确认时登记 unknown 后暂停重试。该路径以宿主的执行前记录衔接事后对账，避免预先登记 unknown 触发同一个交付闸门。

收口时，把交付声明中延期的工作逐条交给 `finish --follow-ups <json>`。每项填 `id`、`summary`，追踪位置填实际工单 URL 或含项目身份的工单号 `ticket`，也可填已 applied 且凭据可核验的 `operation_id`。缺落点时 finish 单列未跟踪项，本地验收状态仍按原条件判定。超出授权时先留本地记录，外部动作按授权推进。

工具不保护恶意改写记录，也不证明所有自然语言技能要求。新增特殊义务需项目契约和适用规则共同复核，规则覆盖之外的硬条件仍保持未满足。

前端事实提取必须显式核对 ui / visual_change / interaction。视觉专项组件来源、预算、复用和最终树证据按 [视觉适配](VISUAL.md)；未提供事实不代表已经检查不适用。
