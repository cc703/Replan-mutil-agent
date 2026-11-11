# P1-C3 归档专项交接

状态：专项实现及定向验证完成，停写等待 root 联合检查和独立 G3；不代表已经验收。计划来源为 temp v001、root G1 PASS。未提交、推送或访问真实 artifacts。

## 文件与接口

- `src/scheduler_core/io/archive.py`：不可变 ArchivePlan/ArchiveResult、规划、源快照重验、确定性 ZIP、双阶段发布及身份和哈希限定回滚；重导出 VerifyResult。
- `archive_record.py`：严格 sidecar、排序摘要、路径及祖先冲突、重复键和严格 schema 校验。
- `archive_verify.py`：只从 archive 命名空间定位，检查 ZIP、记录和内嵌 manifest/config/output，无解压；返回 VerifyResult。
- `archive_publish.py`：Windows MoveFileExW 普通文件无覆盖发布，其他平台 fail closed。
- `tools/archive_run.py`：dry-run、apply、verify；apply 阶段失败返回 4，预检拒绝及既有目标返回 3。
- `tests/unit/io/test_archive_{run,record,verify,publish}.py`、`tests/unit/tools/test_archive_run_cli.py`：专项测试。
- 与 cleanup 协商的 scan_tree 可选 `max_depth=16, max_files=100000` 已由其唯一作者实现并接入；默认共享调用行为不变。

## 实际检查

- `python tools/verify_source.py`：全部 PASS。
- `uv run --python 3.11 --group dev pytest tests/unit/io/test_archive_run.py tests/unit/io/test_archive_record.py tests/unit/io/test_archive_verify.py tests/unit/io/test_archive_publish.py tests/unit/tools/test_archive_run_cli.py -q`：50 passed。
- 同一十个源/测试文件，`uv run --python 3.11 --group dev ruff check ...`：All checks passed；`ruff format --check ...`：10 files already formatted；`mypy --explicit-package-bases ...`：Success，10 source files。
- Windows 临时文件真实探针：MoveFileExW 目标已存在时报错、目标字节和源字节均不变；目标不存在时成功移动。真实临时 junction 测试拒绝且外部哨兵不变。
- 已测各终态、目标单/双存在、源变动、伪造计划、hardlink、坏名称、深度及文件数上限（文件数超限由模拟快照和共享扫描测试覆盖）、目标竞争、阶段读写失败、回滚成功/失败、只读失败警告、相同字节复现、源快照不变、源移走后验证；ZIP 成员增删重复与截断、manifest Git/身份/config/output 不一致、严格 JSON、合法 sidecar 变化及整套自洽重写可通过；真实 CLI 0/2/3/4（4 通过子进程注入阶段校验失败）。
- 联合完整 `tools/check.py` 与 `git diff --check` 由 root 统一执行，未在此并发运行。

## 边界和未决项

验证只保证内部一致，不提供可信签名或防篡改；合法 archived_at、仅记录的空目录和自洽重写可通过。无恶意并发 TOCTOU 承诺；Windows 只读不是防篡改。Linux 未动态测试，归档发布明确 fail closed。中途外部改源不会被回滚。测试覆盖真实 junction/hardlink 与共享安全扫描；未为归档独立构造真实 socket 或真实符号链接，需由 G3 结合共享扫描检查边界。文件数上限未实际创建十万文件；共享扫描早停和归档限值检查以测试替身覆盖。

README 待 root 集成：使用 `python tools/archive_run.py --run RUN_ID [--kind KIND --name NAME] [--root artifacts] [--apply | --verify] [--format text|json]`；默认 dry-run，归档仅 completed，验证无须源运行但只保证内部一致，Windows 本地发布支持、Linux 未验证并 fail closed。

## G3 返工：不可信 ZIP 异常

针对 G3 的 method 99 真实样例，`archive_verify.py` 在读取前拒绝非 ZIP_DEFLATED、加密、压缩补丁和强加密成员；对 Python 3.11 zipfile 的预期 `NotImplementedError`（例如中央目录版本过高）、`EOFError`、`zlib.error` 精确映射 ArtifactError，不捕获所有 Exception。已读本机 Python 3.11 `zipfile._get_decompressor`、`ZipFile.open`、`ZipFile._RealGetContents`、`ZipExtFile._read1/_read2` 实现核查相应异常。

`test_archive_verify.py` 新增真实 ZIP 四种变异：本地及中央目录压缩方法 99、加密标志、非法 deflate 压缩流、过高解压版本；每例同步更新 sidecar ZIP 哈希及字节数，先直接验证原生 zipfile 的相应异常，再调用真实 CLI，断言退出 3、JSON 错误且无 traceback。原自洽重写用例仅把其 ZIP 写入格式改为契约要求的 ZIP_DEFLATED，原成功断言未改。

返工最终 `uv run --python 3.11 --group dev pytest tests/unit/io/test_archive_run.py tests/unit/io/test_archive_record.py tests/unit/io/test_archive_verify.py tests/unit/io/test_archive_publish.py tests/unit/tools/test_archive_run_cli.py -q`：54 passed；针对变动两文件的 ruff check、ruff format --check、mypy 均通过。文件 SHA256：`archive_verify.py` E0D4D3A92E407FB152A147580F02F76329170A01859ED05B879F132B15797ACB；`test_archive_verify.py` 35DAE3E02BBC9BBBDC8108D76D70324F3906C6247CD791A725A1A0B0167B5DD6。专项停写，等待 root 联合检查及独立复测，未提交/推送或触碰真实 artifacts。
