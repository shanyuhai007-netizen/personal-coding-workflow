# 版本记录

## 0.4.18 — 2026-11-20

- 适配 exploration subagent 委派（缺口事实：上游 implement-spec SKILL.md 步骤 2 的 exploration subagent——探查笔记存仓库外共享目录、让实施子上下文专注实现——此前未被 ADAPTERS implement/implement-spec 适配行覆盖，WORKFLOW §1「查事实/探查现状」默认主线程执行，大范围代码库扫读的压力全落在主上下文；2026-11-20 对照 ask-matt/PHASE-BOUNDARIES.md 及上游 implement-spec、code-review 原文复核确认）：ADAPTERS implement/implement-spec 适配行上游步骤补「探查」，执行侧补三条——代码库内探查委派只读子上下文（宿主映射：ZCode 内置 Explore agent、Claude Code Explore 子代理，以会话实际能力为准）；探查笔记存仓库外共享目录供后续子上下文复用、主线程只收结论与指针，笔记归档按 WORKFLOW §5.6 记 hash 指针；无只读子上下文能力时主线程串行探查并记独立性受限。纯文档适配，不改 workflow_rules.json、无规则 hash 变化、无新测试；83 项既有测试全绿。安装副本内容变化，递增补丁版重装三份。

## 0.4.17 — 2026-11-20

- 登记 interrogate 并接 verify 可选义务（缺口事实：两轴评审放行后、由独立核验才抓到实质问题的案例已两例，共同模式是评审把交付者自述当事实放行、未对声明本身做对抗验证——按既定决策规则「第二实例出现即立项」；且阶段组件此前全必需，workflow.py 四处严格相等锁定，把对抗评审接成必需义务会令每次 nontrivial 任务强制多轴对抗，实测成本不可接受；证据存本地评测工作区，不入库）：引擎（a96b200）先行放宽四处严格相等——stage-complete、回执复核、receipt-refile、component-event 统一接受「必需集精确覆盖 ∪ 额外回执 ⊆ optional_components、无重复、degraded 不满足任何义务」的合法集，未配置 optional_components 的规则字节不变、行为不变。本批登记 interrogate（[pstack](https://github.com/cursor/plugins/tree/main/pstack) `skills/interrogate/SKILL.md`，上游 `disable-model-invocation: true`；许可随上游——pstack 子目录自带 MIT LICENSE、上游仓库 license 字段为 null，2026-11-20 实测核实；只登记引用，不捆绑任何第三方内容）并接线 verify `optional_components: ["interrogate"]`：执行则回执与必需同校验（身份、mode、adaptation、verification=pass），不执行不产生义务缺口；上游 disable-model-invocation 语义保持——计划路径不自动触发，接线只给用户显式调用的执行一个阶段回执挂载点。COMPONENTS 新增登记行并在双模式定性段写明接线与 frontmatter 定性的关系；ADAPTERS 新增 pc-0.3 适配行（对手 = cross-CLI reviewers，保存原始输出与 CLI/版本身份；每对手独立 worktree、repro 留在对手 worktree；对抗 brief 核心纪律逐字保留上游原文——"Prove each finding with a run against the real code… Leave out anything you did not run… No findings is a valid result."；verify 口径逐条重跑命令、同根因合并、记 dropped 计数；只报告不修复，发现进 WORKFLOW §5 修复循环）；ROUTING 补可选义务组件路由句；manifest 词表测试同步。规则 hash 变化，在途任务按 EXECUTION 迁移限制处理（旧规则完成或显式 replan）。新增 1 项回归测试（生产规则 verify 可选槽在 plan/next 存在、无 interrogate 回执不阻塞），默认规则集测试更新为仅 verify 可选、其余阶段保持全必需；#3 finish 层兼容验证零代码改动，5 项测试锁定（登记路径义务无关、degraded 双口径、finish 拒绝条件回归），合计 83 项全绿。安装副本内容变化，递增补丁版重装三份。

## 0.4.16 — 2026-11-20

对照三方方法论（Matt 27 skills、poteto verification-skill-example、ECC 6 skills、pstack 58 skills + 22 playbooks 全量逐个阅读，三轮调研 + 两轮把关复核）的准确性批次，全部 P0：

- 双模式定性（缺口事实：COMPONENTS 登记行「引用位置」列对 16 个 Matt skill 声明了 plan 路径接线，workflow_rules 阶段 components 实际只覆盖 5 个——回执义务按阶段 components 严格相等代码级锁定，登记列过度声明了接线；10 个上游带 `disable-model-invocation: true`，设计上就仅限用户显式调用）：COMPONENTS 按 frontmatter 事实（2026-11-20 逐个核对本机 1.3.1 原文）拆三行登记——5 个已接线阶段组件、10 个仅用户显式调用且计划路径不产生组件义务、domain-modeling 可模型调用而未接线——并加定性段：登记在清单与接线进规则是两件事，登记不产生义务。ADAPTERS 适配节加对应段落，用户显式调用与计划路径共用同一适配表。domain-modeling 本批只声明不接线（行为不变，最小改动），接线留给实际需要 glossary 义务的后续版本。
- 适配版本号对齐：COMPONENTS 登记行与 EXECUTION/TOOLS 示例命令滞留 pc-0.2，统一到现行 pc-0.3（ADAPTERS 已是 pc-0.3）；评审发现的 test_evidence 合成 fixture 同步对齐，全仓不再残留 pc-0.2。只改登记、示例与 fixture，历史回执不动。
- feature map 术语锚定（缺口事实：全仓仅 WORKFLOW §4 一处使用该词、无定义锚点，PROJECT.template 对应资产叫「首批 3–5 个 feature 入口」）：以 pstack create-verification-skill 的 feature-map-example（本地克隆逐字核实）升级 PROJECT.template 验证资产节——README 索引（基线前置、驱动约定、证据与跳过申报、feature 清单，清单顺序即 sweep 顺序、覆盖以遍历完清单为准）+ 每特性一个文件固定四 H2（`Sub-features` / `How to get to it (user POV)` / `Driving it with <harness>` / `Gotchas`），只写用户路径与可观察证据、不写实现细节；WORKFLOW §4 该术语改为链接锚定到模板定义，设计参考致谢补 pstack 结构来源并修正其残缺链接。
- doctor 从契约字段升级为阶段前置不变量（缺口事实：PROJECT.template「运行与驱动」节 Doctor 字段早已存在，workflow_rules / EXECUTION / VISUAL / ROUTING 四处 grep 零消费；interaction-verify 树绑定证明代码身份、不证明运行实例身份，0.4.15 接线后浏览器驱动可对过期实例产出截图与报告）：interaction-verify 阶段加 `doctor_check` 门，回执须 `--doctor-check` 附 run 捕获的 doctor 检查，校验与 verify 检查同口径（exit 0、前后树=当前树、日志 hash）；三条全程不变量——意外（驱动失败 / drift / 新会话）后重跑 doctor、已捕获证据在 cleanup 后原位核验、失败残留必清——与「doctor 因 drift 失败修一次重试一次（stage-resume 单周期封顶）、仍败按阶段预算判 blocked」落 VISUAL 与 ADAPTERS web-gui-tester 适配行，EXECUTION 补 `--doctor-check` 语义，PROJECT.template Doctor 字段补消费指针；契约缺 Doctor 字段的项目按缺组件降级，交互条件保持未验。规则 hash 变化，在途任务按 EXECUTION 迁移限制处理（旧规则完成或显式 replan）。新增 3 项回归测试（doctor 前置生效含失败检查拒绝、降级保持未满足且 finish 拒绝、预算耗尽 blocked + 单次 resume 封顶），合计 69 项全绿。安装副本内容变化，递增补丁版重装三份。

## 0.4.15 — 2026-11-20

- UI 运行交互验证接入规则（缺口事实：VISUAL「纯静态截图盲区交给运行交互验证，不以豁免替代」与 verify done_when「交互路径有实际观察」两条义务早已存在，但 workflow_rules 无任何阶段消费 `interaction` 事实——该事实自声明起即为死钩子、全仓零消费；且回执校验按阶段 components 严格相等、拒绝未列义务名，散文点名永远进不了回执机制）：新增 `interaction-verify` 阶段（intents=implement + all[interaction]，components=[web-gui-tester]，after implement/visual-build），并接线进 verify 与 visual-review 的 after——后者补齐 DAG 缺口：critic 消费的截图正是 interaction-verify 的产物，浏览器操作主 agent 专用（control-browser 子 agent 禁用）决定截图只能产自主 agent 阶段。web-gui-tester 为方法论层（原文自声明「用会话实际提供的任何浏览器工具运行、工具规则优先」），工具层按宿主登记（2026-11-20 实测）：ZCode browser-use 插件原生、Claude Code 本机 browser CDP 脚本包（playwright-mcp 未配置、可选另装）、Codex 未配置须实测；无可用工具记 degraded、交互条件保持未验并保留手动复验步骤。`interaction` 定义落 VISUAL（涉及可运行页面实际交互为 true，纯静态微调 false），EXECUTION 前端事实核对句同步加 interaction；ADAPTERS 新增适配行（测试/修复分离 vs WORKFLOW §5 修复循环——受阻路径跳过沿用、缺陷进修复循环不必等 P0-P3 走完；P3 布局/样式发现移交视觉流程不重复评审；环境准备操作报告中申报、真实服务写入前按授权停）并升 pc-0.3；COMPONENTS 登记 web-gui-tester 外部 skill 行与宿主工具层行，manifest 词表测试同步。新增 2 项回归测试（interaction 门控 + verify/visual-review 依赖接线 + 缺回执拒 finish；无事实不激活），既有 UI 用例断言扩展 web-gui-tester，合计 66 项全绿。安装副本内容变化，递增补丁版重装三份。

## 0.4.14 — 2026-11-20

- 回折成本两招（iteration-2 报告 §四.2：回折/失效在 6/6 with run 普遍发生，B 型＝早期回执绑定了任务预定修改的文件——B-w-1 三阶段失效原因均为 index.html 变化，整批机械重录实测 <1min；A 型＝依赖级联——A-w-3 连锁 3 阶段）：① `stage-receipt --pin-input` 在回执落成时把预定修改对象的字节副本封存进 `<回执名>.inputs/`，身份绑定快照而非活文件——预期修改不再使早期回执待验证，快照被改动即失效；tree 绑定阶段（verify、两轴评审、close）不接受 pin，同一文件不得同时 live 与 pin。② 新子命令 `receipt-refile`：file 绑定回执在语义未变仅 hash 变化时以当前 hash 重发，其余字段逐字复制、封存源回执 hash 并记录变更路径，agent 只确认语义；tree/条件绑定的失效必须重做对应工作。③ 依赖级联回升：仅因依赖回折的阶段在依赖恢复且回执仍可验证时自动回升通过（降级与回升均记入 `invalidation_history`/`revalidations`，替代原「整批机械重放 stage-complete」的手工恢复）；计划修订显式要求的 preflight 重核以 `recheck_required` 标记，不被自动回升替代，重新 stage-complete 才清除。
- 阶段级成本记录（iteration-2 报告：subagent_tokens 仅单点总量，6.5M 差值无法按「流程编排 vs 更深验证」分解）：回执落成记 `at` 时间戳；`stage-complete --cost <json>` 接受调用者声明的阶段成本（`tokens`/`duration_ms` 非负数、`basis` 必填自述计量来源），存入阶段 `costs` 并保留 `completions` 完成时刻历史——声明制与全库口径一致，非工具观测。EXECUTION.md 回折成本段按新机制改写（原「预期重开一次、约 15 分钟/次」口径作废），WORKFLOW §5.7 补链接。新增 6 项回归测试，合计 64 项全绿。安装副本内容变化，递增补丁版重装三份。

## 0.4.13 — 2026-11-20

- 把关复核修正（回到一手证据重验 0.4.11/0.4.12 交付声明）：0.4.11 的证据表述补纯度注记——「7 个 grader 一致指出」改为 iteration-2 报告 §三.2 修正版口径（A 侧 6 个 grader 的评分提示含独立重算要求，缺口因此被显著化，判断成立但非纯独立发现），聊天交付摘要中同措辞一并作废。其余声明逐项核验通过：旧套件在 1f2ca77 实跑 54 项、新增 4 项、58/58 属实；commit 时间戳（11-19 23:57/23:59）与条目日期一致，非日期错误；远端 main = 1f2ca77，0.4.8–0.4.10 确已 push、本次两 commit 未 push；三副本 0.4.12 新内容在位，备份每宿主仅留 0.4.10 一份（修剪机制生效）。安装副本内容变化，递增补丁版重装三份。

## 0.4.12 — 2026-11-19

- 独立性替代路径显性化（iteration-2 A-with-3 实证：claude 403 后改用 `codex exec` 造 9 个独立上下文完成两轴评审，stderr 一手痕迹齐备，显著优于「同代理第二遍」）：ZCODE.md 独立性分级把「唯一替代是另开独立会话」扩为两条路径——另开独立会话，或以非交互方式调用其他 agent CLI（codex/claude 等）作为独立上下文来源并保存原始输出；两路径均以 reviewer-id 记录执行身份，跨 CLI 记所用 CLI 与模型/版本身份，并显式声明其边界——同一主体控制下的上下文级独立而非不同评审者，attestation 不得越级，两轴评审仍须不同 reviewer-id。安装副本内容变化，递增补丁版重装三份。

## 0.4.11 — 2026-11-19

- 最小可收口快照（iteration-2 B-with-1 唯一不收敛 run 的根因：visual-review 门在剩余预算 <2min 时进场、90 秒即终止，无 report 无收口声明、3 阶段 pending，而 21:12 回执齐备时刻距合法 BLOCKED 仅一步）：WORKFLOW §5 落规则——进入最后一个高成本门（独立评审、视觉验收等验收类阶段）前先落快照（报告骨架 + 已有证据指针 + 未验项声明），此后每深化一步同步，使 `VERIFIED` / `BLOCKED` 在任意时刻一步可达，预算触顶按快照收口、不追加验证深度。
- 验收数字机械重算（7 个 grader（A 任务全部 6 个 + B-with-2）指出数字可编造、无一致性断言——A 侧评分提示含独立重算要求，缺口因此被显著化，判断成立但非纯独立发现：A-without-1 基线 76.4% 实为 75.6% 且自称「逐一核对」；现有断言编造数字 + 可跑命令即可通过，真实性全靠 grader 手工重算兜底）：acceptance 观测加可选 `numbers` 声明，绑定封存源文件（hash 校验）+ 提取正则 + 重算方式（`count`/`sum`/`mean`/`median`/`min`/`max`/`ratio`，覆盖 B 类「13/13、21/21」计数与 A 类中位数/比例）；两级判据防误报——`exact` 按声明位数四舍五入后一致、`approx` 须落在非负容差内；重算失败的观测降级 `unknown`（对应条件回到未验），不新增硬阶段，源文件事后变化由 hash 拦截。schema 与判据见 EXECUTION.md「原始条件与逐项观测」。新增 4 项回归测试，合计 58 项全绿。安装副本内容变化，递增补丁版重装三份。

## 0.4.10 — 2026-11-19

- description 改为祈使句触发语（iteration-1 实测 recall 0.2：新功能、重构、UI 小改、性能、正式裁决、接手仓库等 8 类查询 0% 触发，模型多直接文本作答）：显式覆盖全部失败意图类别，加入「用户没提工作流、只说帮我修/加/接着做时同样启用」，保留非编码请求排除项。按 skill-creator 优化原则撰写（意图导向、泛化类别、≤1024 字符）；本侧 Claude 端 trigger 复测因代理账户额度不足暂缓（剩余 $1.29 < opus 单次预扣 $1.96），复测命令与 train/test 资产已备好。仅优化 Claude 侧触发语义，ZCode/GLM 侧无 harness 未测。安装副本内容变化，递增补丁版重装三份。

## 0.4.9 — 2026-11-19

- 入口小改分流（iteration-1 成本发现：两个小任务都走全量 evidence 台账，12.9× token / 4.3× 时长）：WORKFLOW.md 落地小改硬判据（既有检查入口可验证 + 单文件 + 单工作单元 + 无正式决策，须全满足），轻量路径最低保留 `run` 检查日志、引用验证结果的本地提交与简短记录，判据失守立即转全路径补台账；SKILL.md 入口与 EXECUTION.md 建立计划节同步引导，消除「入口只通向台账」的结构偏差。
- ZCODE.md 新增独立性分级：无嵌套子 agent 的会话中，硬性独立阶段（formal_decision 事实核验、两轴评审独立上下文、`independent_required`）保持未满足且本会话不可收口，唯一替代是另开独立会话并以 reviewer-id 记录；机械复算可同代理第二遍收口但须声明非独立（iteration-1 评测环境实测无子 agent，此前仅靠回执自觉声明）。
- 安装副本内容变化；与下一版本（触发语优化）合并重装三份。

## 0.4.8 — 2026-11-19

- 安装器备份根治：被替换旧版不再落到技能扫描路径内的同级点前缀目录（该机制每宿主每次重装累积一份，实测已积累 21 份并被 Claude 会话列为陈旧技能副本，为 trigger 欠触发贡献因素），改存 `~/.local/state/personal-coding/backups/<宿主>/<技能名>/<版本>/`（`PERSONAL_CODING_STATE_ROOT` 可重定向，沿用 0.4.1 豁免变量先例），每目录仅保留最近一份、提交后自动修剪，更旧版本从 git 历史找回。恢复逻辑兼容新旧两种事务日志备份路径；新增回归测试断言升级后扫描路径内零点前缀残留且备份仅留一份。安装副本内容变化，递增补丁版重装三份。

## 0.4.7 — 2026-11-19

- 清单校验测试加双向相等断言：解析 COMPONENTS.md 外部 skill 行的名字集合，与测试词表强制相等——登记与词表漏改任一侧即红，消除 0.4.6 引入的双处人工同步点。测试变更本身不涉及安装内容，按惯例递增补丁版保持三副本与源一致。

## 0.4.6 — 2026-11-19

- COMPONENTS.md 补登记 docs/agents/ 配置引用的 5 个 Matt Pocock skill（triage、wayfinder、domain-modeling、grill-with-docs、improve-codebase-architecture），登记范围与 tracked 文档引用范围对齐，消除清单「全部组件逐项登记」承诺下的事实缺口。新增 tests/test_components_manifest.py 机械校验（外部 skill 词表与反引号 slash 调用均须 ⊆ 清单），防止引用漂移再漏登记。安装副本内容变化，递增补丁版重装三份。

## 0.4.5 — 2026-11-19

- COMPONENTS.md 两组件补证完成：modern-web-guidance 为 Google Chrome 团队 npm 包（Apache-2.0，源码仓 GoogleChrome/modern-web-guidance-src），原「Vercel 技能家族」推测不成立已纠正；emil-design-eng 打包者为 Emil Kowalski 作者官方仓 emilkowalski/skills（MIT），本机副本为早期快照已注明。「来源待核实」标记全部清除，登记脚注改为补证口径（npm registry 元数据 + GitHub license，2026-11-19）。安装副本内容变化，递增补丁版重装三份。

## 0.4.4 — 2026-11-19

- 仓库规整审计：无孤儿文件与结构冗余（引用图连通、3649 行全部有职责）；按两处权威规则清除滞留散文版本声明（WORKFLOW 标题、README 两处、COMPATIBILITY 两处），README 版本口径改为指向 VERSION 与 CHANGELOG。.gitignore 补 .DS_Store。本地杂物（.DS_Store、__pycache__）已清理。安装副本内容变化触发版本漂移保护，按 0.2.1 先例递增补丁版重装。

## 0.4.3 — 2026-11-19

- fact-review 改为内部程序：`independent-fact-review` 组件槽位移除——该名称不存在任何上游 skill，原规则下 formal_decision 任务的必需阶段永远无法满足。独立事实核验沿用 WORKFLOW「完成条件先于实施」与 EXECUTION 独立回执（`--independent`），走 output 义务。规则 hash 变化，在途任务需新计划显式复用。
- COMPONENTS.md 升级为全量组件清单：17 个外部组件逐项登记性质、来源、适配与引用位置，modern-web-guidance、emil-design-eng 标记来源待核实（本机副本无作者元数据，不以推测填登记）。ROUTING 与 SKILL 入口补清单指针，缺组件先查清单再查已装技能；README 对应行更新。

## 0.4.2 — 2026-11-19

- 修正 README 与 COMPATIBILITY 中滞留的 0.3.0 散文版本号；版本声明只保留 VERSION 与 CHANGELOG 两处权威，散文一律随发版刷新。

## 0.4.1 — 2026-11-19

- `plan` 与 `finish` 拒绝系统临时目录（/tmp、$TMPDIR 等）作为台账位置；EXECUTION.md 写明持久目录约定，合成测试用 `PERSONAL_CODING_ALLOW_VOLATILE_RECORD=1` 豁免。来自真实会话评审：VERIFIED 任务的证据链曾整体落在待清理的 /tmp。
- `stage-receipt` 的 `--event` 改为可选：组件义务省略时自动匹配本任务最新登记的同阶段/组件/mode 成功事件；`output` 义务（无专业组件，如 close/verify）不再需要事件文件。修复收口必须手写事件 JSON 的断点，并消除挑错事件文件烧 attempts 的簿记失误（实测两台账 13 次 attempt 失败全部属此类）。
- 回灌 0.4.0 安装副本的 drifted 补丁：早期组件回执回折成本的说明、显式 `--event` 的 JSON 校验；三份安装副本统一为 0.4.1。
- 新增 3 项回归测试覆盖上述行为，合计 50 项在 Python 3.10+/本机通过。

## 0.4.0 — 本地候选

- 新增 visual_change、方向/纯视觉实现/最终视觉评审阶段，支持已有实现补验。
- pc-visual-1 规定方向复用、有限修复、缺陷清零或裁决、减法后复验和原始截图证据；不以分数证明品味。
- 不捆绑上游 skill；真实 UI 效果待试点。规则 hash 变化须新计划明确复用，不能直接迁移旧任务。

## 此前未发布

- `plan` 引用项目原始完成条件；`acceptance` 保存逐项观察、目标环境、原始证据和代码树。`finish` 拒绝必要验收缺项/未知/失败及陈旧证据；观测变化使两轴评审与收口待验证。
- 既有两轴评审按相关行为取得原始材料，核对声明范围及外部动作授权；不新增通用事实复核阶段。旧实施计划需显式补齐条件，本地与生产范围沿用原始约定。
- 工具减负仅在仓外小试点，不增加产品命令或删除既有保障；源码仍为0.3.0实验候选，不升级安装副本。
- 修复复合 Bash 命令只校验一种外部动作授权的问题；push、PR创建和合并的匹配动作现逐项校验。
- 新增复合命令授权回归测试；35项合成测试在Python 3.12通过。0.3.0保持实验候选，真实Agent行为与基线对照验收待完成。

## 0.3.0 — 2026-11-18

- 从统一规则生成有依赖的阶段清单；组件义务累计，已有完整实现可跳过重复施工。
- 新增任务身份、来源与事件绑定、输入树失效、独立评审、有限恢复周期和未知副作用对账守卫。
- 增加可选 ZCode Stop/PreToolUse/Read 观察器；仅匹配完整读取和当前绑定session，安装器不改配置、不启用hook。
- 34项合成测试在Python 3.12通过。ZCode.app 3.8.1 bundled CLI 0.16.3 隔离试点使用路径shim与脚本provider，验证缺项反馈、恢复收口和未授权push拒绝。
- 试点不验证真实模型的路由/恢复质量，不代表桌面UI或Claude/Codex原生执行；23条候选评测仍未完整执行。见本地交付记录，不作为公开发布成绩。

## 0.2.1 — 2026-11-18

- 独立评审豁免理由必须为非空字符串，拒绝 null / false / 数组 / 对象；本地试装后遵守版本漂移保护递增补丁版。

## 0.2.0 — 2026-11-18

- 单独开源仓库成为唯一产品源码；保留通用 v0.1 基准历史。
- 加强按阶段加载 / 执行与真实产出记录；明确已有决定、授权及上游人工步骤适配。
- 固定真实工作树的评审输入；独立两轴复核、设计事实及指标语义核验。
- 增加完整命令日志 / 原退出码、组件源 hash / 执行证据、持久归档和记录一致性校验。
- 安装完整 staging 与目录恢复，保留旧版本；修正实例化模板路径约定。
- 16 项合成案例自动化测试本地通过，独立两轴评审发现的 null 独立性开关 / 空执行证明缺口已补回归。
- 新上下文在隔离 CLI 项目完成实际修复、8 项测试及本地提交，无用户提问；这仅证明该任务的显式读取路径。
- GitHub Actions 配置已提供；客户端原生自动选择及三端完整任务仍待单独实测。

## 0.1.0

可移植 Markdown 工作流、专业组件路由、项目 / 任务 / 授权模板与基础本地安装器。作为本仓库最初基准保留。
