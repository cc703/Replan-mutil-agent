# P1-C3 archive 实际派发 v001

配置gpt-6.1-terra / reasoning_effort=high / fork_turns=none。仓库D:/Default/Replan-mutil agent，无旧上下文。你是归档实施专项，不是planner或独立review，不提交/推送/改Git。

用户继续原顺序P1，Claude额度不足即temp代planner。temp v001完整合并方案经root G1 PASS，C2已验收同步；HEAD43b19a42b853fa89878b5f08ab930b4c427c71c3，721 passed/1既有symlink权限skip、68文件静态基线。当前root治理文档与/root/p1c3_cleanup在共享工作树写入各自文件，不覆盖。你仅负责下面归档切片，不做P2/前后端/make_report；B1/solver决策仍延期。

先读AGENTS/PROGRESS/RESUME/model-policy/storage-steward、公共前言与common-delta（历史与当前冲突以最新授权为准）、工程coding-standards/file-storage-standard/open-source-policy/review-gates/git-workflow；运行python tools/verify_source.py。全文读docs/work-packages/p1-c3-temp-plan.v001.md（完整合并契约/所有测试/两prompt）、p1-c3.md末root最终G1。读实际io/artifacts/manifest/paths/errors/cache_publish、pyproject及既有io测试AST。Claude初版仅历史，不把它的已修正承诺重新引入。标准库新API先核已装Python3.11源码/签名和真实临时探针，不引新依赖。

唯一写入集合：
src/scheduler_core/io/archive_record.py
src/scheduler_core/io/archive.py
src/scheduler_core/io/archive_verify.py
src/scheduler_core/io/archive_publish.py
tools/archive_run.py
tests/unit/io/test_archive_record.py
tests/unit/io/test_archive_run.py
tests/unit/io/test_archive_verify.py
tests/unit/io/test_archive_publish.py
tests/unit/tools/test_archive_run_cli.py
docs/agents/handoffs/p1-c3-archive.md
其他全部只读。不要写artifacts.py/maintenance.py/tree_snapshot.py、清理方测试/fixtures/Makefile/README/存储规范、卡片/进度/角色/提示词/Git。归档用法与限制给root在handoff中集成README，禁止并发写说明文件。不新增tests/unit/io/__init__.py，不改旧断言/依赖/锁/布局规则/原文/C1C2行为；需要新职责文件先报告root，不能自行扩白名单。

共享方/root/p1c3_cleanup已固定接口：
from .tree_snapshot import scan_tree, TreeSnapshot, TreeEntry
scan_tree(root: Path) -> TreeSnapshot
frozen TreeSnapshot(root: Path, entries: tuple[TreeEntry,...])
TreeEntry(relpath: str, kind: Literal['file','directory'], size: int, mtime_ns: int, mode: int, device: int, inode: int)
包含根项relpath='.'，entries按relpath排序，属性total_bytes/file_count/last_activity_ns。扫描拒绝链接/reparse/hardlink/特殊文件/非法命名，抛UnsafePathError。共享源码正在落盘，先写与你独立的archive_record/普通文件发布及测试，勿把暂缺导入当最终通过。API补充先向共享方和root说明，由唯一作者改共享文件。归档限制≤100000文件、深度≤16必须在写任何归档产物前检验；如需在扫描时早停，向共享方请求可选参数，不擅改其文件。测试helper若尚未稳定直接在已授权测试文件保留少量fixture，不新增未授权helper。

为共享Maintenance延迟委托提供下列稳定API（如确有不可行请先协调）：
archive.py定义并导出frozen ArchivePlan、ArchiveResult、VerifyResult（VerifyResult可从archive_verify重导出但不循环）；plan_archive(store: ArtifactStore, run_id: str, kind: str|None=None, name: str|None=None)->ArchivePlan；apply_archive(store: ArtifactStore, plan:ArchivePlan, now:datetime)->ArchiveResult。
archive_verify.py提供verify_archive(store:ArtifactStore, run_id:str,kind:str|None=None,name:str|None=None)->VerifyResult；验证只从archive命名空间定位zip/sidecar，不能依赖源运行仍在磁盘。若类型放archive_record.py并从archive.py re-export更清晰可以如此，但必须通知共享作者导入位置。两个作者协调自己负责的入口，不覆盖对方。

完整语义/验收按temp v001+root G1：只completed，源只读不改不删；plan/dry-run不创建任何目录；归档输出路径从绑定store派生，伪造ArchivePlan不可写别处；安全扫描拒junction/hardlink等、manifest/config/output完整。ZIP固定时间/权限/排序与压缩级别，在同环境相同输入可复现；sidecar严格JSON/类型/重复键/字段、原manifest原字节SHA，内容摘要按约定。verify读zip内Manifest.model_validate_json并独立对应路径身份/Git/config/output，不调用依赖磁盘源的read_manifest，不解压。

verify只保证内部一致性，合法archived_at变化、仅侧文件记录的empty_directories和整套自洽改写可能通过，测试实证并如实写限制；不得恢复“任意sidecar字段修改必检出”。不引入签名/服务。失败注入外部改了源时工具不擅自回滚该改动，源不变保证指工具自身不写源。

先真实验证已装Windows普通文件no-replace和目标已存在字节不变，不根据C2目录docstring推断，也不改C2cache_publish。源快照重校验、两stage回读、zip/sidecar任一存在均拒绝；先zip后sidecar发布，第二步失败只有身份+哈希仍属本次发布才回滚，否则PARTIAL_ARCHIVE；stage失败清理、回滚失败保留报告、chmod只读失败告警。无恶意并发TOCTOU承诺，Linux未动态验证不冒称支持。不rmtree/不跨shell递归删除。所有删除前验证绝对目标限于本次临时root/归档stage或自己发布的文件，绝不作用真实artifacts。

新增测试必须覆盖temp v001所有archive/verify/publish/CLI相关验收、合法变化可能通过、身份/manifest/Git/config不一致、目标竞争不覆盖、两文件发布/回滚失败、只读告警、深度文件上限、源不变、真假CLI退出码/JSON/dry-run字节不变与非法root/非法run定位。只tmp_path或系统临时数据，不新增skip/xfail、不削弱旧断言。

按职责保持可读，函数/文件长度审查参考而非凑行；完整类型/docstring，不引抽象框架。先定向pytest与ruff/format/mypy相应文件，双方源码稳定后联合一次完整uv run --python 3.11 --group dev python tools/check.py、git diff --check，不机械重跑无变化的全量。每条实际命令/结果、文件用途、API差异、平台探针和已知限制写指定handoff，向root报告；DONE只是切片交付，独立G3/G5仍待执行。
