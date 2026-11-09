# P1 独立审查交接（分阶段）

日期：2026-11-09（Asia/Shanghai）；角色 reviewer v001；实际派发配置 gpt-6.1-terra / high / fork_turns=none。工作包 OSS-1、P1-0；审查提示词 p1-review.v001。本人未参与被审包实施。

## 阶段 0：档案前置 — PASS

四份提示词的 BEGIN/END 标记内正文按 UTF-8 计算 SHA256，均等于其声明值，且与所声明的渲染捕获行逐字相等：

| 提示词 | 捕获行 | payload SHA256 |
|---|---|---|
| p1-contract.v001 | v001:16–64 | 0cf0a2a515c9ada943f6ecdf1b489b4e89ce7b3aec2c945c14aa33c3a97bc302 |
| p1-oss.v001 | v002:42–91 | 3cb33168792343ef951c5555ea7a14e921b37f7608b0e5e43bfd2987ef368b8c |
| p1-contract.v002 | v002:95–164 | f416d1c94ca4121bb12c61735ae3cabb33d53911a891a4914e6eb4ce22d38d8f |
| p1-review.v001 | v002:168–216 | 67a3da623333b5b87194f572e8d29d1cd6f9300eb8e1742108f2921d3162a36b |

捕获全文 SHA256 分别为 v001 `8cf708c392eab40333dadc0bd84b722f76a64a02af51d7479327586453ea0831`、v002 `5f95467e7f6bfd38b95769b2ac356604562226ffb3bd2b3d9be140e5b21355a9`，与四个摘录头部记录一致。证据仅证明仓库渲染捕获与摘录一致，不证明原始 Markdown 字节或外部会话独立真实性。

Git 状态及 diff 显示七份已跟踪旧提示词无改动；四份新摘录与捕获、派发日志属于总设计师归档。已观察到的其他共享树改动为总设计师登记的进度、索引与日志文件；OSS 正在执行，审查阶段不能据未交付认定失败。上述检查为时点快照，不代替后续交付后的范围复核。

G1 的分阶段审查将 OSS 工程 G3 ACCEPT 与需要远程同步的整体状态区分，提案依赖前者，未发现循环；未授权代码实现、依赖安装或批准契约。实际派发日志记录 OSS 与本审查使用 Terra/high/fork none，文件范围与 G1 表一致；提案尚未派发。日志中本 reviewer 消息与本次收到的任务一致；实际模型配置依据派发记录，无法从审查文档独立核实运行时底层模型。

发现：本阶段无阻断发现。G1 的等价类、默认字段与缓存解释须在后续交付审查中按原文覆盖和实际生成文件再次检验，前置 PASS 不代表被审交付 ACCEPT。

## 后续状态

- OSS-1：IN-PROGRESS，交付和工程 G3 **待审**；许可证表与外部来源尚未核对。
- P1-0：**NOT-STARTED**，待 OSS 工程 G3 ACCEPT；引用表、V7、兼容性和 G4 未决表尚未审查。
- 用户 G4：PENDING；任何建议均非批准。远端同步暂缓。

## 本次验证和交接

- `python tools/verify_source.py`：三份原文 bytes、lines、sha256、encoding、LF 及全部 14 批 PASS。
- Python 标准库 hashlib 对四份 payload、两份捕获和行范围比对：均一致；`git status --short`、`git diff --name-only`、`git ls-files docs/agents/prompts` 核对上述范围。
- 未运行完整治理检查、pytest、ruff、mypy 或布局检查；总设计师报告的基线结果不是本人执行结果。
- 本次仅新增本交接文件，用于保留分阶段审查证据；无被审文件修改。未发现需立即提交的新用户裁决；后续 G4 由完整提案审查汇总。
- 下一步：等待总设计师 followup，在 OSS 交付后独立复核；不自行进入提案阶段。

## 阶段 1：OSS 工程 G3 — REWORK

**发现 R1（重要，阻断工程 ACCEPT）**：`docs/planning/p1-oss-research.md:26,44,61` 将 Hypothesis 的 MPL-2.0 写为须审查及新增依赖须授权，但没有明确指出依 `docs/engineering/open-source-policy.md`，未来引入 MPL 候选须先向用户提交 G4 裁决及链接方式、修改范围、分发方式、替代方案；一般授权/审查不应被误读为已完成该特定门禁。建议作者补充明确前置与状态（本轮仅参考，未引入；未来 G4 PENDING），无需现在提前要求用户批准。固定版本 [官方许可证](https://github.com/HypothesisWorks/hypothesis/blob/v6.170.15/LICENSE.txt) 和 [PyPI 元数据](https://pypi.org/pypi/hypothesis/6.170.15/json) 为 MPL-2.0 证据。

### 独立核对表（2026-11-09）

| 条目 | 独立来源与结果 |
|---|---|
| OR-Tools | [v9.15 tag](https://api.github.com/repos/google/or-tools/commits/v9.15) 解析为 `551ad10d94835c99e5e1e684500d3db398c0e345`；三个文档所列固定 Python 示例与根 Apache 2.0 LICENSE 的 raw 文件可读取；[固定递归树](https://api.github.com/repos/google/or-tools/git/trees/551ad10d94835c99e5e1e684500d3db398c0e345?recursive=1) 5121 项、truncated=false，文件名无 NOTICE。 |
| PyJobShop | [v0.0.9 tag](https://api.github.com/repos/PyJobShop/PyJobShop/commits/v0.0.9) 解析为 `5e1cbee697f44ca451fcdd8c6fb97bec151930d5`；根许可为 MIT；[固定递归树](https://api.github.com/repos/PyJobShop/PyJobShop/git/trees/5e1cbee697f44ca451fcdd8c6fb97bec151930d5?recursive=1) 137 项、truncated=false，文件名无 NOTICE。Model.py、ProblemData.py、solve.py 可读取；solve.py 默认 ortools、可选 cpoptimizer；所读模型与数据文件无 skill 字样，有 allow_breaks。具体 breaks 的边界与 setup 细节本轮尚未独立逐条复核，需补查，不凭名称推断。 |
| 依赖与许可 | 直接读取 PyPI 的最新 JSON 和所列固定 JSON：pydantic 2.14.3、numpy 2.5.4、pytest 9.2.0、hypothesis 6.170.15、ortools 9.15.6755 为服务返回最新版；候选 requires-python、所列 Windows cp311/纯 Python wheel 与日期均与表一致。pydantic 强制 core==2.50.4，core 有 cp311 Windows wheel；Hypothesis pytest extra >=4.6。读取五个固定源码许可文件：Pydantic/pytest MIT、NumPy 根 BSD、Hypothesis MPL、OR-Tools Apache；NumPy 分发表达式另含 0BSD/MIT/Zlib/CC0。NumPy 最新 wheel 发布日期待独立补查；pytest/OR-Tools 旧元数据 license_expression 为空，其根许可文本为依据。 |

递归树结果仅覆盖仓库文件名而非文件内容和发行包；本包无复制或安装授权。分发包额外许可、传递依赖、Windows 安装与动态联测均 NOT-RUN，不作为此元数据研究的验收前提。

### 实际检查与范围

本 reviewer 运行：`python tools/check_repo_layout.py` → Layout PASS；`python tools/check_import_boundaries.py` → Imports PASS；`python tools/verify_source.py` → 三原文和 14 批 PASS。`uv run --python 3.11 --group dev python -m pytest -q -p no:cacheprovider tests/governance` → 33 passed、1 skipped（symlinks unavailable）、1 warning（禁用 cacheprovider 后未知 cache_dir），7.98s；`uv run --python 3.11 --group dev ruff check . --no-cache` → All checks passed；`uv run --python 3.11 --group dev ruff format --check . --no-cache` → 6 files already formatted；`uv run --python 3.11 --group dev mypy tools` → 4 source files 无问题。设置 PYTHONDONTWRITEBYTECODE；mypy 缓存指定 artifacts/tmp。检查非业务验收。作者交接如实披露 check.py 内 pytest 未关闭 cacheprovider，后续已单独指定选项重跑；本 reviewer 未运行 check.py。

相对 8a5914d，已跟踪变化为 root 的 dispatch-log、registry、PROGRESS，未跟踪交付为作者两份文件；共享树不能把 root 合法变更当作者越界。无依赖、锁、源码、原文或测试变化。此后本 reviewer 只追加本报告。P1-0 仍 NOT-STARTED，G4 待完整提案；OSS 的 REWORK 修正和上述未完成的细节复核后再作工程 G3，工程 G3 不等同远程同步状态。

### 阶段 1 补核完成

对前表标为待核的项目继续直接读取官方文件：[ProblemData.py:15–22](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L15) 检查非负、起点小于终点、只在前终点大于后起点时拒绝，故允许相接；[同文件:211–213](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L211) 描述 allow_breaks 的中断和恢复；[同文件:534–535](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L534) 声明 setup 可在 machine breaks 内发生。[NumPy 2.5.4 PyPI JSON](https://pypi.org/pypi/numpy/2.5.4/json) 的 wheel 上传 UTC 日期为 2026-10-10，与稿件一致。这两项待核已解除；工程结论仍为 **REWORK（R1 待作者补充）**。

### 阶段 1 R1 定向复审 — 最终工程 G3 ACCEPT

复核 `docs/planning/p1-oss-research.md:67–71` 与 `docs/agents/handoffs/p1-oss.md:31–35`：明确 Hypothesis 的 MPL-2.0 在未来实际引入前须经用户 G4，状态 PENDING，裁决材料须说明链接方式、修改范围、分发方式和替代方案；候选替代仅供比较，明确不擅自移除原规格要求或改变评估协议。R1 已解决，未见新增矛盾。此前 REWORK 保留为真实审查历史。

OSS 工程 G3 **ACCEPT**；可进入 P1-0 文档提案。此结论不授权安装、复制代码或冻结业务契约，也不代表用户 G4 或 Git 远端同步已完成。Windows 动态安装联测及发行包额外许可仍为 NOT-RUN/未核验，未来引入前处理。此次仅执行定向文档阅读与 `git status --short`；不重复前次已完成的网络与治理检查。

## P1-0 工程 G3：REWORK（2026-11-09）

本结论针对四份文档交付，非用户 G4；P1-A 未授权。独立审查发现以下阻断事项，需作者修订后再复审；不自行修改被审文件。

1. **重要：三项人员占用边界无法作明确裁决。** `docs/planning/p1-contract-proposal.md:19,55`、`docs/decisions/0006-personnel-contract-proposal.md:7` 将人员是否占设备准备时间、DONE 历史占用、冻结 person 只写成待裁决，清单中的开放日历/subcode 选项并不回答这三项。分别给选项、推荐、影响和不裁决后果，可合并为一个裁决条目但不能合并掉各自的选择；说明 DONE 的历史与当前计划范围以及冻结 person 与 V8/V11 的关系均未定，不应暗设。
2. **重要：字段舍入与现行 TimeAxis 接口不闭合。** `docs/planning/p1-contract-proposal.md:46,57` 提议按字段方向取整，但 `docs/source/codex_spec_v1.1.original.md:280–285` 的 `to_slot(dt)` 无字段或方向参数，duration 也不是 datetime。需将转换位置/接口方案（例如保留通用接口并在导入层显式区分，或提议具语义参数/专用转换）及契约影响、推荐与边界例子列为 G4；不可把任意一种接口当已决定。舍入后窗口不可行与输入非法/求解不可行的边界也应明确为可审查选项。
3. **重要：工作包卡片不具备可操作的范围与门禁。** `docs/work-packages/p1-contract-review.md:3` 以“提案、ADR、本卡、交接”概称输出，未给四个精确授权路径及其只读/禁止范围，也未列 G0–G5 的责任和当前状态、失败回退/修订路径。Claude 提示词 `docs/agents/prompts/p1-contract.v002.md:67` 要求文件清单、输入、验收、依赖、阻塞；`docs/engineering/review-gates.md:5–16` 定义门禁。补齐路径、验收和适用门禁状态，保留本地提交与远端暂缓的真实边界，避免将 G3 与整体同步混同。
4. **重要：矩阵缺可复核的完整端到端示例。** `docs/planning/p1-contract-proposal.md:27–39` 分层逻辑覆盖缺分配、未知、技能、互斥、日历，但大量行仅描述单维条件；未给可复制核对的最小旧 JSON 缺省案例、带完整 person/task/assignment 的可选人员冲突与阻塞正反例。补足代表性等价类的具体输入及预期（含可选分配、空/非空阻塞、未知引用与旧 JSON），明示短路/非短路和每条 P1 拟测范围；无需生成不可能全笛卡尔积。
5. **重要：RUNNING/V10 候选尚不够可裁决。** `docs/planning/p1-contract-proposal.md:48` 只称按当前预计 end 校验或统一 duration，未写明拟采用的等式、不等式、缺来源如何处理、已开始任务实际开始与原 duration 的关系；无法核对原候选的 end ≥ start + duration 与 latest new_end 等条件能否满足真实事件。补充各候选判断表和超时/提前结束等边界，注明调用方传值仅为路线建议，数据形状、持久性和具体 API 均未定；不得把推荐当前来源用作其他条款已成立前提。

### 引用、模型和兼容性核对

规格第 3 节实查为 21 个 BaseModel（TimeAxis 至 ReplanResult）与 Slot、Event 两别名，`docs/work-packages/p1-contract-review.md:11–33` 均有对应项目与起始行，未发现漏项或重编号。已对照交接所列 S:278–285、287–338、340–430、443–446 与 D:211–217、224–228、357、441、448–456、462、555、584、753–762；逐项支持时间/人员/事件、NEGOTIABLE、H7–H10 与 V2/V5/V7–V11 的引用，未发现误引；S、D 别名定义见提案第 3 行，ADR 行号为同文件延续。文字对 V7 编号保持不变，缺人员/未知人员失败、可选人员校验、阻塞式空日历无阻塞、旧字段缺省的原则成立；具体示例覆盖仍需按发现 4 补充。人员非法输入错误归属明确待裁决，不等同 V7 已批准。

### G4 未决核对

| 项 | 推荐与未决 | 前提检查 |
|---|---|---|
| 人员字段、技能集合与需求开关 | 有推荐，待用户裁决 | 未声称已批准；旧数据需补示例 |
| 日历、V7 detail、准备/DONE/冻结 person | 前两项有推荐，后三项缺各自选项和推荐 | 阻断 R1 |
| V2/V9、需求与准备/阻塞占用 | 分流与占用有推荐 | G4 PENDING |
| 时间取整、时区及接口 | 舍入有推荐，接口缺方案 | 阻断 R2 |
| solve_initial 返回 | 结构化结果有推荐 | G4 PENDING |
| RUNNING 当前 end | OPEN-DATA-SOURCE；调用方传入为暂定路线 | 推荐≠批准，缺候选判定细节，见 R5 |
| 冻结 end/V11 | OPEN-DATA-SOURCE；有证据例外为推荐 | 推荐≠批准，需来源可追溯 |
| NEGOTIABLE 凭证 | OPEN-DATA-SOURCE；默认硬+显式授权为推荐 | 推荐≠批准，现有字段不足 |
| Hypothesis | 未来 MPL 引入前专项 G4 PENDING | 本提案不引入 |

三个 OPEN-DATA-SOURCE 均标未决，未发现其他条款明确将其推荐宣称为已决定；人员准备、DONE、冻结 person 及时间接口的独立裁决必须补充完整。B1 与双 profile 保持 DEFERRED-BY-USER。

### 实际验证与范围

本 reviewer 设置 PYTHONDONTWRITEBYTECODE、mypy 缓存 artifacts/tmp，实际运行 `python tools/check_repo_layout.py` 和 `python tools/check_import_boundaries.py` 均 PASS；`python tools/verify_source.py` 三原文、14 批 PASS；`uv run --python 3.11 --group dev python -m pytest -q -p no:cacheprovider tests/governance` 为 33 passed、1 skipped（symlinks unavailable）、1 warning（禁用 cacheprovider 后 unknown cache_dir），7.95s；`uv run --python 3.11 --group dev ruff check . --no-cache`、`ruff format --check . --no-cache`、`mypy tools` 分别通过、6 files already formatted、4 source files 无问题。仅治理验证，非业务测试或 P1 完成。

对 f145a1a 的 Git 状态：四个未跟踪提案交付属作者范围；root 合法变动为 dispatch-log、registry、PROGRESS 及新增派发文件；未发现依赖、锁、源规格或测试被修改。作者交接公开说明 `tools/check.py` 内部 pytest 未禁用 cacheprovider 并单独复跑；本 reviewer 未运行该入口。上述 Git 检查为时点快照；本人仅追加此交接。建议作者修订 R1–R5、补充真实交接，再交独立复审。

## P1-0 R1–R5 定向复审（2026-11-09）：REWORK

复审四份最新交付，保留首轮历史。R1、R2、R4、R5 已解决；R3 文件范围和门禁大部已补齐，仍有一处需澄清后才能工程 ACCEPT：

- **R1 CLOSED**：主提案人员占用边界对准备、DONE、冻结 person 分别给出选项、推荐、影响及阻塞；ADR 同步，V8/V11 区分为建议而非批准。
- **R2 CLOSED**：字段转换位置/接口与 duration 单列方案；已有对齐与非对齐示例、非法输入、预检查不可行、求解不可行及超时未知区分，原 `to_slot(dt)` 非整槽行为仍明确待裁决。
- **R3 OPEN（重要）**：`docs/work-packages/p1-contract-review.md:57` 写“G5 需 G3 通过且 G4 已解决或 N/A，再……本地提交”，但 `docs/work-packages/p1-claude-review.md:41` 明确用户裁决前完成可评审提案、独立检查与本地检查点；此措辞使 G4 未决时的本地检查点是否能提交不清楚，并可能阻止 G1 授权的裁决前保存。请明确区分裁决前的文档本地检查点与 G5 完整验收/同步，保留远端暂缓和 G4 不阻塞独立文档工作的条件。四个精确路径、权限、G0–G5 责任与返工路径其余已补充。
- **R4 CLOSED**：三个 JSON 已以标准库 `json.loads` 解析；逐项检查旧模型必填字段、时槽处于 horizon、任务工期与示例区间一致，t0 为带时区 UTC；可选人员的相接、阻塞、未知引用、缺分配、互斥和技能变体及短路规则已列，均仅声明人员层结论。
- **R5 CLOSED**：三种 RUNNING 判定以 s、d、e、c 表述并有超时/提前预测边界；缺 c 推荐未验证且阻止正式展示提交，调用方传入仅属来源路线建议，类型、API、事件排序、持久化与重放未定。原先的 `end≥start+duration` 为可选路线而非隐含前提，未声称用户已裁决。

G4 依然全部未决：人员字段/集合技能/显式开关推荐；阻塞式日历、V7 detail、人员仅执行占用、DONE 当前视野内历史与冻结 person 保持及 V11 表达推荐；V2/V9 按容量分流和准备需求/阻塞占满容量推荐；保守取整、拒绝 naive、外部适配转换与预检查不可行推荐（通用 to_slot 非整槽行为仍待决定）；solve_initial 结构化结果与现有 None 的迁移待决定；三个 OPEN-DATA-SOURCE 分别为 RUNNING 当前 end 来源及判断（暂推荐调用方来源和候选 A）、冻结 end/V11 有证据例外、NEGOTIABLE 默认硬与显式放宽凭证，均推荐≠批准。Hypothesis MPL 未来引入前独立 G4 PENDING。上述建议不授权 P1-A、安装、复制或冻结契约。

本次执行 Python 标准库提取并解析三段 JSON，核对实例及计划必填字段与视野内槽范围，均通过；并用 `git status --short` 检查共享树，作者四份交付仍未跟踪、root 与 reviewer 合法文件并行修改，未发现依赖/原文/源码更改。未重新运行网络或全套治理检查；首轮真实结果见上。本人只追加本审查文件。请作者澄清 R3 后定向复审。

## P1-0 最终定向复审：工程 G3 ACCEPT（2026-11-09）

R3 CLOSED：`docs/work-packages/p1-contract-review.md:57` 现明确 G3 后、G4 PENDING 时可保存提案文档本地检查点，且不代表业务批准、完整 G5 或远端同步；业务实施和完整 G5 仍以 G4 已解决或 N/A 为前提，与 `docs/work-packages/p1-claude-review.md:41` 一致。作者交接记录了此次修订。此前 R1、R2、R4、R5 均已 CLOSED；前两轮 REWORK 保留为真实历史。

`docs/planning/p1-contract-proposal.md:3,57,75` 中，裁决项 4 与补充正文一致：推荐通用 `to_slot` 拒绝非整槽，由外部适配层按字段保守舍入；仍为 PROPOSED、G4 PENDING。未发现此次修订引入新的阻断矛盾。定向复审实际读取工作包、作者交接和提案相关段落并检查 `git status --short`；未重复先前已记录的治理测试和网络核查。

最终结论：P1-0 文档工程 G3 **ACCEPT**，可由总设计师准备用户 G4 裁决与本地文档检查点。G4 仍包括人员字段与需求、准备/DONE/冻结 person、V7、设备容量、时间转换、solve_initial 及三项 OPEN-DATA-SOURCE（RUNNING 当前 end、冻结 end/V11、NEGOTIABLE 授权数据）；具体推荐及替代见前表与提案，均未批准。Hypothesis 未来引入另有 MPL 专项 G4。此 ACCEPT 不授权 P1-A 实施、冻结契约、安装或复制，也不表示远端同步；用户裁决前只推进不依赖业务决定的工作。
