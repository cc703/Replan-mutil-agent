# P1-C3 Claude 初版（2026-11-11）

来源：https://claude.ai/chat/54ab7bfe-2bca-4714-9759-e3ae3e5474e7，消息88；页面Sonnet 5.5 Medium。以下为实际文章DOM innerText的语义排版转录：去除按钮、图标、时间及工具运行装饰，恢复标题、表格和代码块；不是原始Markdown文件。完整计划、公共契约与两份提示词均保留。消息87提供root核验摘要及原文摘录；Claude没有本机文件访问。其关于自己spec副本的核对是Claude原话，不冒称本地root额外验证了Claude环境。回复完成后页面明确额度耗尽，提示14:40恢复；未升级、未重复发送。

## P1-C3 清理与归档：计划、契约与提示词

以下为提议，供 root 审 G1。我没有读过本机文件，下面的依据只来自你提供的摘要，以及我这里的 spec 副本。spec 副本的 sha256 与你给的一致，第 2.6 节 215–223、第 2.7 节、P1 行（551–554）我都已逐行核对。

### 一、缺口与工程决定

没有需要向用户确认的信息缺口。以下几项必须由实施 Agent 在编码前读源码确认，不构成阻塞：

- io/paths.py 中的公开函数名（_is_link 是私有的）。
- ArtifactStore 是否有公开的 root 属性。
- C2 的 cache_publish.py 是否支持普通文件的“目标存在则失败”语义。
- 现有 tools/check.py 如何导入 src。

我替你定下的工程决定，root 可在 G1 否决：

- 清理和归档都默认 dry-run，只有加 --apply 才改动文件系统。
- failed-runs 的 --older-than 不得低于 14d，低于则报错，不静默放宽。
- running 运行永不按年龄删除，超期的只在 stale_running 中报告，不提供删除或“标记中断”能力。
- INDEX 保护用“完整 run_id 子串加名称级路径”，有意偏向过度保护。
- 归档不覆盖、不删除源运行、不提供解压；另提供只读的 --verify，它是归档后回读校验的同一套代码。

给将来 make_report 的约束：INDEX 必须写入完整 run_id，写入 README。

### 二、写入范围

| 角色 | 精确文件 |
| --- | --- |
| 实施（新建源码） | src/scheduler_core/io/retention.py、index_refs.py、removal.py、archive_record.py、archive.py；tools/clean_artifacts.py、tools/archive_run.py |
| 实施（新建测试） | tests/unit/io/test_cleanup_policy.py、test_cleanup_references.py、test_cleanup_apply.py、test_archive_run.py；tests/unit/tools/test_clean_artifacts_cli.py、test_archive_run_cli.py（及按惯例的 __init__.py） |
| 实施（修改） | Makefile（仅 clean-tmp 目标，不新增 apply 目标）；README.md（短用法）；docs/engineering/file-storage-standard.md（只补命令行为说明，不改规则）；docs/work-packages/p1-c3.md；docs/agents/handoffs/p1-c3.md |
| 条件限定 | io/paths.py：仅当 ruff 或 mypy 拒绝包内导入 _is_link 时，新增一个公开别名，不改行为；io/artifacts.py：仅当缺少公开只读 root 时增加属性；tools/layout_rules.toml 与 tools/check_import_boundaries.py：仅当确认拒绝新文件才做最小修改，禁止全局豁免。各自须在交接单说明且补测试 |
| 独立审查只写 | docs/agents/handoffs/p1-c3-review.md |
| root 单写 | 进度、CHANGELOG、RESUME、registry、提示词归档、Git（chm 提交，cc703 普通 push，核验远端 SHA） |

禁止改：tools/check.py、models、axis、validate*、generation*、generate.py、C1 与 C2 既有 io 行为与断言、docs/source、实例缓存。

新增 io 模块遵守 C1 的约束：不依赖 numpy、models、random、ortools、validate。

### 三、契约 CB-C3（两个提示词都引用）

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
  (b) 含 "artifacts/runs/<kind>/<name>" 且其后为结尾或非 [a-z0-9_-] 字符（名称级引用保护该名称下全部运行）。
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
    sidecar 发布失败而 zip 已发布：仅当该 zip 哈希仍等于自己写入的哈希才删除，否则报告 PARTIAL_ARCHIVE 并保留；
  8 发布后尽力设只读，失败只告警 READONLY_NOT_APPLIED。
不覆盖发布：先读 C2 的 cache_publish.py，若其明确支持普通文件的"目标存在则失败"则复用，否则 os.link 加 unlink；
  两者都须有 Windows 真实测试证明"目标已存在则失败且目标字节不变"；其他平台 fail closed。
绝不删除或修改源运行，不提供解压。
--verify：只读，核对 zip 与 sidecar（archive_sha256、条目名、大小、逐条目哈希、content_sha256、sidecar 严格解析），不解压到磁盘。
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

### 四、实施提示词

```text
[附公共前言、增量 v002、契约 CB-C3] 运行配置：gpt-6.1-terra，推理 high，fork_turns=none。你没有先前上下文，以下为全部背景。

# 角色与目标
P1-C3 实施 Agent。实现 artifacts 的清理与归档。简单完整，按职责分文件，函数约 20–60 行、文件约 150–300 行（仅作参考，不为压行排版）。
完整类型与 docstring（输入、返回、异常、边界），Python 3.11，Pydantic v2，只用标准库与已有依赖。不提交、不推送、不改 Git。

# 允许写入
src/scheduler_core/io/retention.py  index_refs.py  removal.py  archive_record.py  archive.py
tools/clean_artifacts.py  tools/archive_run.py
tests/unit/io/test_cleanup_policy.py  test_cleanup_references.py  test_cleanup_apply.py  test_archive_run.py
tests/unit/tools/test_clean_artifacts_cli.py  test_archive_run_cli.py（及 __init__.py）
Makefile（仅 clean-tmp）  README.md（短用法）  docs/engineering/file-storage-standard.md（只补行为说明）
docs/work-packages/p1-c3.md  docs/agents/handoffs/p1-c3.md
条件限定（须在交接单说明并补测试）：io/paths.py 公开别名、io/artifacts.py 公开只读 root、layout_rules.toml 与 check_import_boundaries.py 的最小修改。
其余只读。禁止：改 tools/check.py、models、axis、validate*、generation*、generate.py、C1 与 C2 既有行为与断言、docs/source、实例缓存；
新依赖；numpy、random、models、ortools、validate 导入到新 io 模块；把终端业务逻辑塞进核心生成器；新增 skip 或 xfail；
真实 artifacts/ 上执行 apply 或生成归档。B1 外移与双 profile 保持延期。

# 先做（结果记入交接单）
1 uv run python tools/verify_source.py。
2 读源码并记录：io/artifacts.py、manifest.py、paths.py、errors.py、cache_publish.py、tools/check.py（导入 src 的方式）、
  Makefile、tools/layout_rules.toml、现有 tests/unit/io 的 AST 扫描与命名惯例、docs/engineering/file-storage-standard.md 的清理与保留规则。
3 在本机 Windows 实测：只读文件的 unlink 行为；os.link 在目标存在时的行为；cache_publish 对普通文件的行为（若复用）。

# 任务（按顺序，每步跑全量测试）
1 retention.py 与 index_refs.py：只读，无任何修改文件系统的调用（测试用 AST 断言）。
2 removal.py：按 CB-C3 第 5 节；不使用 rmtree。
3 tools/clean_artifacts.py。4 archive_record.py、archive.py（含 verify）。5 tools/archive_run.py。6 Makefile 与文档。
接口名称可调整，语义为契约；调整须在交接单说明。

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
  --verify：篡改一个字节、截断 zip、多余条目、缺条目、sidecar 字段被改、sidecar 多余字段或重复键 → 失败；正常通过；
  失败注入：zip 写入中、回读校验中、源文件在归档中途被修改（SOURCE_CHANGED）、sidecar 发布失败（清理自己的 zip）、目标在发布前被他人创建（不覆盖，其字节不变）；
  每次失败后无 stage 残留，源运行不变；
  含符号链接、junction、硬链接、特殊文件、坏文件名、超过限制的运行被拒；archive 目录链上有 junction → 拒绝；
  run_id 在多个 kind 下重复 → 要求消歧，指定后成功；unknown run_id 报错；
  zip 条目名全为 "<run_id>/…"，无 ..、绝对路径、反斜杠；archive.py 无 extract 与 extractall（AST）。
cli：退出码 0、2、3、4 各一例；JSON 输出键固定且可解析；dry-run 输出确定性；Makefile 的 clean-tmp 命令文本为 clean_artifacts.py --kind tmp --older-than 7d；
  在无 artifacts 的空目录运行 → 退出码 3，且不创建 artifacts。
全局：新增 io 模块通过现有 AST 扫描；测试产物只在 tmp_path 或系统临时目录；不新增 skip 或 xfail
  （Windows 专属测试用平台条件，Windows 基线不产生 skip）。

# 验收命令（真实输出写入交接单）
uv run --python 3.11 --group dev python tools/check.py
uv run --python 3.11 --group dev python -m pytest tests/unit/io tests/unit/tools -q -p no:cacheprovider
uv run --python 3.11 --group dev python tools/check_repo_layout.py
uv run --python 3.11 --group dev python tools/verify_source.py
git diff --check
git diff --name-only
基线：721 passed 加 1 个既有 Windows symlink 权限 skip，68 个文件的静态检查全过；新增后基线不降，skip 仍为 1。

# 验收标准
行为与 CB-C3 一致；每个边界、反例都有真实断言；dry-run 字节不变；apply 只删合格目标；归档逐文件哈希与源不变；
diff 只含允许文件；无新依赖；无敏感与运行产物入库；条件限定改动（如有）已说明。

# 交接
公共前言 H 格式，另附：读源码结论；Windows 实测结果；接口名称与契约的差异；各限制（无 TOCTOU 承诺、Windows 只读标志、
Linux 未动态测、stale running 仅报告、INDEX 过度保护、sidecar 发布失败时的 PARTIAL_ARCHIVE）；行数表；模型、推理档、fork 模式。
```

### 五、独立审查提示词

```text
[附公共前言、增量 v002、契约 CB-C3] 运行配置：gpt-6.1-terra，推理 high，fork_turns=none。
角色：P1-C3 独立 G3 审查。只读，只写 docs/agents/handoffs/p1-c3-review.md，不读作者会话。
命令加 -p no:cacheprovider；探针与 CLI 只在仓库之外的系统临时目录进行，不得触碰真实 artifacts/，不得在仓库产生文件。

审查项
1 范围：git diff 只含允许文件；tools/check.py、C1 与 C2 既有行为和断言、models、validate*、generation* 未变；无新依赖；无新增 skip 或 xfail；
  条件限定改动（如有）仅为最小增补且有测试；新 io 模块不 import numpy、random、models、ortools、validate。
2 独立复现 tmp 年龄：自行构造目录，仅子文件较新而目录自身很旧；用 os.utime(ns=) 验证"恰等于不合格、多 1 纳秒合格"；未来时间；
  UNSAFE_ENTRY（junction、硬链接）；BAD_NAME；确认 retention.py 与 index_refs.py 不含修改文件系统的调用。
3 failed-runs：ended_at 依据；running 永不删除且仅 stale 报告；completed 永不出现在候选；损坏 manifest；14d 下限；确认没有借用 Run 的内部方法清理终态运行。
4 INDEX：自写不少于 12 种 INDEX 文本探针（表格、代码片段、链接、反斜杠路径、名称级、兄弟运行、过度保护、CRLF、BOM、NUL、非 UTF-8、超大、目录、junction）；
  核对 fail-closed，退出码 3，无删除；核对 README 已写明 INDEX 写入方必须写完整 run_id，且没有宣称能识别缩写或口头引用。
5 apply 安全：对 junction 指向仓库外目录做真实探针，目标外哨兵文件保持；计划后注入 junction；
  Windows 只读删除只影响目标子树；root 非法各类；apply 前确认不会创建 root；
  失败注入后 partial 报告与剩余路径正确，其他目标继续，退出码 4；removal.py 无 rmtree；
  确认 dry-run 前后树快照逐字节相同。
6 归档：核对 zip 的确定性、条目名与权限、sidecar 严格解析与字段、content_sha256 与 archive_sha256 的重算；
  重跑三种拒绝场景；篡改与截断被 --verify 检出；失败注入后无残留且源运行不变；
  不覆盖发布在 Windows 上对已存在目标失败且目标字节不变（核对作者交接单的证据并自行复现）；archive.py 无解压；源运行从不被删除或修改。
7 CLI 与文档：退出码 0、2、3、4；JSON 键；Makefile 的 clean-tmp；README 与 file-storage-standard 的描述与实际行为一致，未改规则语义；
  所有限制已如实披露（无 TOCTOU 承诺、Windows 只读非防篡改、Linux 未动态测、stale running 仅报告、INDEX 过度保护）。
8 重跑全部验收命令并记录真实输出；与 721 passed 加 1 skip 的基线核对。
结论 ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、建议）；探针的真实输出；未能核实项；模型、推理档、fork 模式。
```

### 六、流程与两点提醒

流程：root 审 G1，通过后派发实施，再派发独立 G3，最后 G5。G5 为最终全量 check，更新进度、CHANGELOG、RESUME，以 chm 提交，用 cc703 普通 push 并核验远端 SHA。若未核验成功就写“未同步”，不要写成已同步。

范围外：真实归档不在本包执行，论文未定稿；工具只交付能力，make_report 与 P2 不在本包。

提醒：

- 把“stale running 仅报告”这一点单独告诉用户，因为 spec 写的是“status ≠ completed 保留 14 天后可清”，本包出于安全没有对 running 实现清理。后续若需要处理崩溃遗留的 running 运行，要另做“标记中断”的包。
- --verify 虽不在 spec 里，但它与归档后回读校验是同一套代码，保留可以避免多写一份。
