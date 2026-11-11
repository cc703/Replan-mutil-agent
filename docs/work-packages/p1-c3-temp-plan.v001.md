# P1-C3 temp 计划 v001：待 root G1

本文件为 temp 输出，不是 Claude 批准；以下契约及补充条款共同构成合并方案。

```text
# 1 通用
范围：清理只处理 artifacts/tmp 的一级条目与 failed、partial 运行；归档只处理 completed 运行。
不动：instances（C2 缓存）、archive 既有内容、completed 与 running 运行、llm_traces、logs。
默认 dry-run；--apply 才修改。年龄用整数纳秒比较，now 为 UTC aware，可注入，默认当前时间。
age 语法 ^[1-9][0-9]*[smhdw]$（re.ASCII，≤3650d）；"older than"为严格大于：age_ns > older_than_ns 才合格，恰好相等不合格。
kind=failed-runs 要求 older_than ≥ 14d（低于则 ValueError）；kind=tmp 要求 >0。
省略 --older-than：tmp 为 7d，failed-runs 为 14d。

# 2 tmp 条目
对象：root/tmp 下一级的每个条目；root/tmp 本身永不删除；缺失则空计划。
依据：条目及全部后代 lstat.st_mtime_ns 的最大值 last_activity，不跟随链接（仅看目录自身 mtime 是错误的）。
跳过并报告：FUTURE_TIME（last_activity > now）；BAD_NAME（条目名不符 relative_path 规则）；
  UNSAFE_ENTRY（子树内有符号链接、junction、reparse point、硬链接 nlink>1、套接字或设备等非普通文件或目录）。

# 3 failed-runs
对象：root/runs/<kind>/<name>/<run_id>，kind 属 experiment、sim、agent_eval。
read_manifest 读取失败 → MANIFEST_INVALID，跳过并报告，绝不删除。
status failed 或 partial：依据 ended_at；FUTURE_TIME 跳过；被 INDEX 保护则列入 protected，不删。
completed：永不清理。running：永不按年龄删；started_at 早于 now−14d 的仅列入 stale_running，需人工处理。
形态不符的条目 NOT_A_RUN；含链接、硬链接、特殊文件、非规范文件名则 UNSAFE_ENTRY 或 BAD_NAME，跳过。

# 4 INDEX 保护（fail-closed）
路径默认 docs/results/INDEX.md，可 --index 覆盖。
absent：文件不存在 → 无已登记引用，报告 INDEX_ABSENT，不是错误。
unreadable（拒绝一切删除，退出码 3）：非普通文件、链接或 reparse point、读取失败、非严格 UTF-8、含 NUL、大于 1 MiB。
保护：文本先把反斜杠换成斜杠，再做大小写敏感的子串匹配（有意偏向过度保护）：
  (a) 含该运行的完整 run_id；
  (b) 含 "artifacts/runs/<kind>/<name>" 即保护该名称下全部运行（包括完整路径）。
披露：只会多保护（如 …small-light 被 …small-light-2 的引用保护），不会漏掉字面出现的 run_id 或路径；
  不承诺识别缩写、大小写变体、口头描述。apply 开始时重新读取 INDEX，不信任 dry-run 结果。

# 5 apply（清理）
前置：root 必须已存在且是目录（先检查，不得调用会创建 root 的构造）；root 自身不是链接或 reparse point；
  拒绝文件系统根，以及含 .git 或 pyproject.toml 的目录；root 至 tmp、runs 的链路逐层无链接。
每个合格目标（按路径排序）：重新 lstat、重读 manifest、重判资格、保护与安全，任一变化 → CHANGED_SINCE_PLAN 跳过。
删除只作用于该目标子树，自底向上：文件先 chmod 可写再 unlink，目录 rmdir；不使用 rmtree，不跟随任何链接；
  遇到链接立即中止该目标并报告；绝不 chmod 目标之外的路径；manifest.json 最后删除。
单个目标失败不影响其他目标，整体退出码 4；部分删除标 partial 并列出剩余路径；输出 deleted、skipped、failed、partial。
不承诺 TOCTOU 安全；Windows 只读标志不是防篡改；Linux 路径未动态测试须披露。

# 6 归档
对象：status=completed 且 read_manifest 通过的运行；按 --run 在 runs/*/* 下定位，匹配多个须用 --kind 与 --name 消歧，0 个报错。
源目录必须只含规范命名的普通文件与目录，无链接、硬链接、特殊文件；文件数 ≤100000，深度 ≤16；违反则拒绝且不创建任何归档产物。
输出：root/archive/<kind>/<name>/<run_id>.zip 与 <run_id>.archive.json，路径逐层经 ArtifactStore 的守卫，禁止链接。
zip：标准库，ZIP_DEFLATED 固定级别；条目名 "<run_id>/<相对 POSIX 路径>"，排序，无目录条目，无绝对路径与 ..；
  ZipInfo 时间固定 1980-01-01，权限固定只读；相同输入得到相同字节。
sidecar（ArchiveRecord，pydantic strict、extra=forbid、键排序、末尾换行）：
  schema=1、tool_version="c3-1"、run_id、kind、name、source_relpath、status="completed"、source_manifest_sha256、
  git_commit、git_dirty、archived_at（UTC，clock 可注入）、archive_filename、archive_sha256、archive_bytes、file_count、
  content_sha256、entries[{path,size,sha256}]（排序）、empty_directories（排序）。
  content_sha256 = 按 path 排序拼接 "path\0size\0sha256\n" 后取 SHA256。
流程（--apply）：
  1 校验运行并记录源目录快照（相对路径、大小、mtime_ns）；
  2 目标 zip 或 sidecar 任一已存在 → ARCHIVE_EXISTS，拒绝，不覆盖、不比较、不重建；
  3 边读源文件边算 SHA256，写入同目录 stage-*.part；
  4 回读 stage：testzip、条目名集合与预期完全一致、逐条目重算哈希与大小一致、无多余条目；
  5 再次校验源快照与 manifest 未变，否则 SOURCE_CHANGED 并清理 stage；
  6 写含 archive_sha256 的 sidecar stage；
  7 先发布 zip，再发布 sidecar，均为不覆盖发布；失败则清理自己的 stage；
    sidecar 发布失败而 zip 已发布：仅当文件身份与哈希仍等于本次发布的文件才删除，否则报告 PARTIAL_ARCHIVE 并保留；
  8 发布后尽力设只读，失败只告警 READONLY_NOT_APPLIED。
不覆盖发布：选取经实际验证的普通文件 no-replace 原语；不得仅凭 cache_publish 目录文档推断普通文件支持；
  须有本机真实测试证明普通文件目标已存在则失败且目标字节不变；未验证或不支持的平台 fail closed。
绝不删除或修改源运行，不提供解压。
--verify：只读，按下方内部一致性条款核对 zip、manifest 与 sidecar，不解压到磁盘。
默认 dry-run：只列计划文件、大小、目标路径，不写任何文件。

# 7 CLI 与退出码
python tools/clean_artifacts.py --kind {tmp,failed-runs} [--older-than AGE] [--root artifacts] [--index docs/results/INDEX.md] [--apply] [--format text|json]
python tools/archive_run.py --run RUN_ID [--kind K --name N] [--root artifacts] [--apply | --verify] [--format text|json]
退出码：0 成功；2 用法错误；3 拒绝（INDEX 不可读、root 非法、存在冲突）；4 apply 有失败或部分完成。
dry-run 不得创建、修改或删除任何文件或目录（含 root、tmp）；输出按路径排序且可复现；
输出含解析后的绝对路径、依据时间、年龄、字节数、文件数、原因；JSON 键固定。
Makefile 的 clean-tmp 改为 clean_artifacts.py --kind tmp --older-than 7d（dry-run）。
工具脚本导入 src：先看 tools/check.py 的做法并沿用；若无，则在 main() 内先把 src 加入 sys.path 再导入，不使用 noqa 或 type: ignore。
```




## 存储入口、校验边界与职责

原始设计哈希通过。用户授权 Claude 额度不可用时 temp 暂代计划，root 审 G1 后才能实施。verify 只保证严格结构和内部一致，不能承诺 sidecar 任意更改必检。严格解析 JSON（拒重复键、非法数、额外字段），对 zip 内 manifest 原始字节先用严格 JSON 和已有 Manifest 模型校验，再依据 zip 内成员检查 config SHA 和 outputs（不调用要求磁盘目录的 read_manifest）；核对目标路径与 zip 顶层 run_id、内嵌 manifest 的 run_id/kind/name/status/git.commit/git.dirty、config SHA 和 outputs；逐项验证 zip 字节、条目、大小、哈希、数量和 content_sha256。empty_directories 仅检查排序、唯一、规范及与文件不冲突，无法证明原有空目录；archived_at 仅能校验合法 UTC。合法更改它或整套自洽改动可能通过，绝不宣称防篡改。测试需同时证明非法/不一致必拒和上述合法变更可能通过。

INDEX 保守保护任意出现完整 run_id、规范完整运行路径或名称级路径的运行，名称级前缀出现即保护该名称全部运行；对归一化后的每次 `artifacts/runs/` 出现，提取至空白、括号、引号或 Markdown 分隔符；若 token 不是 `artifacts/runs/<合法kind>/<合法name>` 加可选完整 run_id 和后续规范路径，或含 `%`、反引号内断行、反斜杠转义、问号及片段符，则停止所有删除，不可读同样 fail-closed。apply 前重新读 INDEX、重扫目标及 manifest，变化跳过；不在真实 artifacts apply。

提供 `ArtifactStore.open_existing(root, *, clock=None)`：检查既有绝对 root、链、非盘根且不含 .git 或 pyproject.toml，不创建任何目录；原构造行为不变。`store.maintenance()` 返回无写入的维护入口，提供 `plan_cleanup(kind, older_than, index, now)`、`apply_cleanup(plan, index, now)`、`plan_archive(run_id, kind, name)`、`archive(plan, now)`、`verify_archive(run_id, kind, name)`，返回不可变类型化结果：CleanupPlan 含 kind、older_than、now、index、items（各含绝对路径、依据时间、年龄、大小、文件数、引用、原因、快照）；CleanupResult 含 deleted/skipped/failed/partial 与剩余路径；ArchivePlan 含运行身份、绝对源/目标、大小、文件数与快照；ArchiveResult 含目标、状态、告警；VerifyResult 含身份、检查结果和原因。路径、安全、解析错误抛 ArtifactError 或 ValueError，CLI 映射约定退出码；CLI 通过入口，不绕过 ArtifactStore。`tree_snapshot.py` 只读扫描并提供安全树、mtime_ns、类型、大小、文件身份、排序；拒绝链接/reparse/hardlink/特殊文件。maintenance 协调，retention/index_refs 只读，removal 安全删除，archive_record 严格格式，archive_verify 核验 zip，archive_publish 做普通文件 no-replace，archive 编排。既有 paths 与 cache_publish 不改；现有目录发布功能不可未经验证宣称普通文件支持。

发布前本机真实探测普通文件 no-replace 与目标存在字节不变；不支持或未验证平台 fail-closed。两 stage 回读、重验源后先发布 zip 再 sidecar；第二步失败只在文件身份与哈希均与本次发布一致时尝试回滚，否则报告 PARTIAL_ARCHIVE，失败清理自己 stage；竞争、回滚失败和 chmod 只读失败均做实质测试。禁止跨 shell 删除；不承诺恶意并发 TOCTOU 安全，Windows 只读非防篡改，Linux 未动态测试须披露。

## 实施提示词

你是独立实施专项 gpt-6.1-terra/high/fork_turns=none，目录 D:/Default/Replan-mutil agent。读 AGENTS、PROGRESS、RESUME、公共前言、工程规范、原文及 p1-c3 卡、Claude 初版与本计划，先运行 python tools/verify_source.py。实现本文件完整契约和末尾全部测试清单，不删除旧断言、不新增 skip/xfail、不引入依赖。运行定向测试后执行 `uv run --python 3.11 --group dev python tools/check.py`、`git diff --check`、`git diff --name-only`，与 721 passed/1 既有 skip 基线对照并真实记录；不机械重复无变化的全量。仅测试 tmp_path 或系统临时数据，论文定稿前不对真实产物 apply，保留源运行；无提交或推送。交接报告实际命令、平台探针、边界和未验证项。

精确写入：`src/scheduler_core/io/{artifacts,maintenance,tree_snapshot,retention,index_refs,removal,archive_record,archive,archive_verify,archive_publish}.py`（artifacts 仅增加 open_existing 和 maintenance）；`tools/{clean_artifacts,archive_run}.py`；`tests/unit/io/{maintenance_fixtures,test_maintenance,test_tree_snapshot,test_cleanup_policy,test_cleanup_references,test_cleanup_apply,test_archive_record,test_archive_run,test_archive_verify,test_archive_publish}.py`；`tests/unit/tools/{test_clean_artifacts_cli,test_archive_run_cli}.py`；`Makefile`（仅 clean-tmp）、`README.md`、`docs/engineering/file-storage-standard.md`（仅行为说明）、`docs/agents/handoffs/p1-c3.md`。不新增 tests/unit/io/__init__.py；禁止修改路径规则、原文、既有测试、C1/C2 既有行为。root 单写卡片、进度、CHANGELOG、RESUME、registry、提示词及 Git。若拆分实施，先由单一作者负责 artifacts、maintenance、tree_snapshot 和对应测试；清理方只负责 retention/index_refs/removal/clean CLI 及对应测试，归档方负责 archive*、archive CLI 及对应测试；README/Makefile 指定唯一作者，共享文件禁止并发写。

## 独立 G3 提示词

你是未参与实施的独立审查 agent，gpt-6.1-terra/high/fork_turns=none，仅读取相同资料与实际 diff，仅写 `docs/agents/handoffs/p1-c3-review.md`。审查白名单、ArtifactStore 入口、旧断言、原保留规则、真实 dry-run 无写入及源不变；独立复现本文件测试清单中的正反测试，特别关注 INDEX 歧义、损坏 manifest、时间边界、链接、并发目标、普通文件发布与回滚/只读失败。验证 manifest/Git/config 和身份一致性，以及合法 archived_at、空目录和整套自洽更改的可检出边界；不得声称防篡改。只用临时目录，重跑完整 check 与必要定向测试，记录实际命令、平台限制及证据，以 ACCEPT / REWORK / ESCALATE 报告文件行号、未核实项；不修复、不提交。

## G1 待核验

root 审核保留规则、覆盖条款与初版冲突、公开接口与 ownership、INDEX 歧义处理、发布/回滚和验收完整性。计划尚未 G1 PASS，未实现。已知不抵抗恶意并发 TOCTOU；running 只报告，zip/sidecar 无外部可信锚。



## 完整测试验收清单

# 必须新增的测试（tmp_path；断言精确到值与原因代码；真实 CLI 用 subprocess 与 sys.executable；绝不触碰真实 artifacts/）
树快照助手：记录 (相对路径, 类型, 大小, mtime_ns, 权限, SHA256)，用于证明"不变"。
policy：age 语法非法 ""、"0d"、"-1d"、"7"、"7x"、"1.5d"、"3651d"、全角数字、空格；failed-runs 的 13d 被拒、14d 通过；
  tmp：条目与目录；目录自身 mtime 很旧但内部有新文件 → 不合格（递归最大值）；
  恰在边界（age 等于 older_than）不合格，多 1 纳秒合格；未来 mtime → FUTURE_TIME；空 tmp、缺 tmp；tmp 目录本身永不出现在候选；
  BAD_NAME；含符号链接（尝试创建，无权限则不 skip，改用 monkeypatch 的链接检测）、junction、硬链接 → UNSAFE_ENTRY；
  failed 与 partial 以 ended_at 计算，边界与未来时间；completed 永不候选；running 即使 started_at 很旧也永不候选并出现在 stale_running；
  损坏 manifest → MANIFEST_INVALID 且不删；NOT_A_RUN；run 目录含链接或坏文件名被拒。
references：无 INDEX、有 INDEX；run_id 出现在表格单元格、代码片段、链接目标、Windows 反斜杠路径；名称级路径保护该名称下全部运行；
  只引用兄弟运行时其他运行不受保护；"small-light 被 small-light-2 引用保护"的过度保护用例（断言受保护并注明为设计）；
  INDEX 是目录、符号链接或 junction、非 UTF-8、含 NUL、超过 1 MiB、读取失败 → unreadable，退出码 3 且无任何删除。
apply：真实 CLI dry-run 前后树快照逐字节相同，且不创建 root、tmp；--apply 只删合格目标，保护的、未达龄的、completed、running 均保留；
  Windows 只读文件可被删除且目标外的权限与文件不变；root 非法（缺失、文件、盘符根、含 .git、含 pyproject.toml、root 自身是链接）→ 退出码 3，未创建目录；
  在 apply 计划之后改动目标（新增文件、状态变化、出现保护）→ CHANGED_SINCE_PLAN 跳过；
  junction 指向仓库外的目录：该目录及其中哨兵文件保持原样，目标被跳过或中止；计划后才放入 junction 同样不被跟随；
  失败注入（monkeypatch removal 中的 os.unlink 在第 N 个文件抛 PermissionError）→ 标记 partial，列出剩余路径，其余目标继续，退出码 4，目标外无任何删除；
  removal.py 无 rmtree（AST）。
archive：完整流程：多层目录的 completed 运行，zip 条目名集合等于源文件集合，逐条目哈希、大小、content_sha256、archive_sha256 与 sidecar 一致；
  相同输入（相同 clock、git）两次归档字节相同；源目录快照归档前后不变；dry-run 不写任何文件；
  只允许 completed：running、failed、partial、损坏 manifest 均被拒且不创建任何产物；
  重跑：zip 与 sidecar 都在、只有 zip、只有 sidecar 三种均拒绝且既有字节不变；
  --verify：篡改一个字节、截断 zip、多余条目、缺条目、sidecar 与 zip 或内嵌 manifest 不一致、sidecar 多余字段或重复键 → 失败；正常通过；
  失败注入：zip 写入中、回读校验中、源文件在归档中途被修改（SOURCE_CHANGED）、sidecar 发布失败（清理自己的 zip）、目标在发布前被他人创建（不覆盖，其字节不变）；
  每次失败后无 stage 残留，源运行不变；
  含符号链接、junction、硬链接、特殊文件、坏文件名、超过限制的运行被拒；archive 目录链上有 junction → 拒绝；
  run_id 在多个 kind 下重复 → 要求消歧，指定后成功；unknown run_id 报错；
  zip 条目名全为 "<run_id>/…"，无 ..、绝对路径、反斜杠；archive.py 无 extract 与 extractall（AST）。
cli：退出码 0、2、3、4 各一例；JSON 输出键固定且可解析；dry-run 输出确定性；Makefile 的 clean-tmp 命令文本为 clean_artifacts.py --kind tmp --older-than 7d；
  在无 artifacts 的空目录运行 → 退出码 3，且不创建 artifacts。
全局：新增 io 模块通过现有 AST 扫描；测试产物只在 tmp_path 或系统临时目录；不新增 skip 或 xfail
  （Windows 专属测试用平台条件，Windows 基线不产生 skip）。


追加：合法 archived_at 和合法 empty_directories 改动可能通过；完全自洽重写可能通过；manifest 身份/Git/config/outputs 不一致必须失败。普通文件发布冲突、双阶段发布失败、身份核验后回滚与 chmod 失败均要测试。INDEX token 截断、编码和歧义 fail-closed。


## API 类型及 INDEX 精确定义

`plan_cleanup(kind: Literal["tmp", "failed-runs"], older_than: str | None, index: Path, now: datetime | None = None) -> CleanupPlan`；`apply_cleanup(plan: CleanupPlan, index: Path, now: datetime | None = None) -> CleanupResult`；`plan_archive(run_id: str, kind: str | None = None, name: str | None = None) -> ArchivePlan`；`archive(plan: ArchivePlan, now: datetime | None = None) -> ArchiveResult`；`verify_archive(run_id: str, kind: str | None = None, name: str | None = None) -> VerifyResult`。所有 now 必须 aware，转换 UTC；None 使用 store clock。清理计划不可作为授权：apply 按当前 root、INDEX、树和 manifest 重新计算并比较快照。各 result 的 items 均按绝对路径排序；大小为普通文件字节和，数量为普通文件数。清理候选的 reason 至少包含 ELIGIBLE、TOO_YOUNG、FUTURE_TIME、BAD_NAME、UNSAFE_ENTRY、MANIFEST_INVALID、NOT_A_RUN、PROTECTED、CHANGED_SINCE_PLAN、STALE_RUNNING；报告所有候选与跳过原因。各公开 API 只持有绑定 store，不接受由外部传入的任意 root；CLI 对无效参数返回 2，路径/保护/冲突拒绝返回 3，执行部分失败返回 4。

INDEX 读取严格 UTF-8（可接受 BOM）、大小不超过 1 MiB，NUL/链接/非普通文件/读取错误拒绝；缺失报告 INDEX_ABSENT。先将反斜杠替换为斜杠。只对字面 `artifacts/runs/` 做机械解析：其后的 token 读到空白、`< > ( ) [ ] " ' `（反引号）任一字符为止；token 的 kind 必须为 experiment、sim、agent_eval，name 必须满足 C1 命名正则，之后可无剩余段，或包含完整的现存合法 run_id，再加规范相对路径。空段、缺 kind/name、未知 kind、`%`、`?`、`#`、不匹配现存完整 run_id 的截断或多余不合法路径均令 INDEX_UNREADABLE，整个 apply 拒绝；这有意保守。直接完整 run_id 子串仍保护相应运行。名称级引用及其前缀按字面子串保护该名称所有运行，因此多保护可接受；不能识别未包含字面前缀及完整 run_id 的缩写、变体或口头描述，文档明确登记必须含完整 run_id。机械反例覆盖缺段、未知 kind、百分号、问号、片段、无效路径和短 run_id，测试拒绝并无删除。

`tests/unit/io/maintenance_fixtures.py` 为唯一新增测试辅助，生成合规 run、树快照和失败注入；由共享作者独占。由于 `tests/unit/io` 不新增包初始化，测试通过 pytest fixture/conftest 机制或同目录可导入方式使用；若现有测试发现无法稳定导入，则复制少量 fixture 到各测试文件，删除该辅助，不增加其他文件。以上模块与测试文件的允许集合即最终写入白名单。
