# 版本记录

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
