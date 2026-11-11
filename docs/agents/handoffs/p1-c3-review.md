# P1-C3 独立 G3 中间交接

派发 gpt-6.1-terra/high/fork_turns=none；当前 REWORK，审查尚未完成，非最终验收。

## P1 不可信 ZIP 不受控异常

`src/scheduler_core/io/archive_verify.py:145-146` 调用 ZIP testzip，只捕获 OSError、ValueError、KeyError、BadZipFile。不支持的压缩方法抛 NotImplementedError，穿透 `tools/archive_run.py:39`，CLI 返回 1 并输出 traceback，而不是预期拒绝码 3。受影响精确版本 SHA256：archive_verify.py `34a29fd6d921bf58a9df432312aFAE2c64e2f8e68bf17182191a783fb87f8d8c`；test_archive_verify.py `2dfe9a244f245d951b71622b6eecf35d7ec11964db1062409eaddbdaF00b1d0d`；tools/archive_run.py `f8c310533adff7512921883c6ff920796b615f2201f36ff89c6a215a40daF8ff`。

真实独立探针：PowerShell 设置 PYTHONPATH=src，通过 `uv run --python 3.11 --group dev python -` 在 TemporaryDirectory 中调用测试构造函数创建真实 completed archive；将 ZIP 第一个本地头 offset +8 和中心目录头 offset +10 的压缩方法改为 99；更新 sidecar 的 archive_sha256 和 archive_bytes；运行 `python tools/archive_run.py --root <temp>/root --run <run_id> --verify`，子进程返回 1，stderr 结尾 `NotImplementedError: That compression method is not supported`。仅系统临时目录，无真实 artifacts。建议将不可信 ZIP 解码/不支持方法及损坏流异常映射为 ArtifactError，并以真实构造输入覆盖 CLI 码 3；不要笼统吞掉无关程序错误。

来源验证 python tools/verify_source.py PASS。完整 check 已启动；其余范围及修后版本待审，未完成前不得 ACCEPT。

## 初审其他结果

独立全量 `uv run --python 3.11 --group dev python tools/check.py`：836 passed、1 skipped（原 Windows symlink unavailable），layout/import/source PASS，ruff PASS，format 90 files，mypy 90 files PASS；这是返工前快照，不作为返工后证据。`git diff --check` 退出 0。

独立 INDEX 探针：系统 TemporaryDirectory 内调用 `read_index`；表格、代码、完整链接、反斜杠路径、名称级、前缀过保护及 BOM/CRLF 均正确保护；兄弟名称不保护；截断 ID、百分号、片段、查询、NUL 均拒绝；缺失返回 absent；非 UTF8 和 1048577 字节均拒绝，全部 PASS。审阅 maintenance.py、retention.py、index_refs.py、removal.py、tree_snapshot.py；未完成全部要求的独立安全探针，不构成该范围全面通过。

系统临时目录真实 `os.utime(ns=...)`：父目录旧于子文件时 basis 使用子文件时间；恰好一天 TOO_YOUNG；请求旧 1ns 时文件系统实际向下量化 99ns，结果 ELIGIBLE；不能声称真实文件系统精确 1ns 已验证。

## 返工后复核与新增独立证据

返工后 `archive_verify.py` SHA256 `e0d4d3a92e407fb152a147580f02f76329170a01859ed05b879f132b15797acb`，对应测试 SHA256 `35dae3e02bbc9bbbdc8108d76d70324f3906c6247cd791a725a1a0b0167b5dd6`。重复真实 method 99 并更新侧文件归档哈希；另将首成员压缩数据首字节改为 ff 并更新哈希：两者 CLI 均返回 3，stderr `archive verification failed`，无 traceback。原问题在这两个具体输入上已解决。

修后独立执行 `uv run --python 3.11 --group dev python tools/check.py` 退出 0：840 passed、1 原 symlink unavailable skip；layout/import/source PASS、ruff PASS、format 90 文件 PASS、mypy 90 文件 PASS；`git diff --check` 退出 0。实际模型派发 gpt-6.1-terra/high/fork_turns=none。

系统临时目录真实 Windows MoveFileExW：目标存在时 FileExistsError，源和目标原始字节不变；目标不存在时源移走、目标字节为源。真实硬链接扫描拒绝且文件内容不变。缺失 root 被拒且未创建；伪造 ArchivePlan zip_path 指向外部哨兵被拒且哨兵字节不变。清理/归档计划前后独立记录路径、文件字节、mode、mtime 一致。真实 ZIP 独立逐项重算大小和 SHA，manifest 原字节 SHA 匹配；成员已排序，固定时间 1980-01-01 00:00:00，权限字段 33060，正常 verify 通过。该 ZIP 检查脚本未关闭 ZipFile，临时目录清理时 Windows 拒绝删除打开的 ZIP，脚本最后退出非零；这些检查结果在异常前已打印。随后针对精确临时路径的清理尝试被自动策略拒绝，遗留 `C:\Users\zhaoyun\AppData\Local\Temp\tmp2tvst2vx`，未触及真实 artifacts。

## 当前结论和限制

初始具体缺陷已修复；完整独立 G3 尚未完成，不能 ACCEPT。未独立构造或逐项核实本派发要求的所有边界：真实 junction 与 socket、failed/partial/running 的全组合、cleanup apply 重验/部分删除和失败后 junction、全部发布竞态与回滚故障、各类严格 sidecar、源消失后验证及完整 CLI 退出码/树快照等。全量测试通过是补充证据，不等同于上述独立探针。请 root 继续安排完成这些审查后决定 G3；当前交接为未完成，不代表新发现的实现缺陷。

最终交接结论：ESCALATE（审查覆盖未完成，需后续独立补审；并非认定已修复缺陷仍存在）。临时目录清理自动审批工具返回 `rejected: blocked by policy`，未提供更具体原因；没有尝试绕过。该遗留因探针自身持有 ZIP 句柄，属于审查脚本问题，不是产品缺陷。

## 补审完成及最终结论（取代此前 ESCALATE）

结论 **ACCEPT**。此前发现的 verify 异常修复已复测；此前未完成的六类补审现已完成，未发现新的可执行缺陷。修后完整检查记录仍有效；再次核对 archive_verify.py 与 test_archive_verify.py SHA256 分别为 `e0d4d3a92e407fb152a147580f02f76329170a01859ed05b879f132b15797acb`、`35dae3e02bbc9bbbdc8108d76d70324f3906c6247cd791a725a1a0b0167b5dd6`，未变化；`git diff --check` 再次退出 0。审阅 archive、record、verify、publish、maintenance、tree、retention、removal、index 和两个 CLI 的实现及相应测试；清理、归档模块分别负责安全候选与删除、严格元数据与发布、无解压验证，CLI 负责参数和退出码映射。

以下为本轮独立 Python 3.11 探针，均用 `uv run --python 3.11 --group dev python -`，各自使用新系统 TemporaryDirectory：

1. 真实 Windows `cmd /c mklink /J` 在已规划的临时清理候选内创建指向外部哨兵的 junction；scan_tree 抛 UnsafePathError，apply 报 CHANGED_SINCE_PLAN，外部哨兵字节保持 `safe`。清理前对该已知 junction 单独 rmdir。当前 Python `socket.AF_UNIX` 不存在，因此真实 socket 未构造；以 lstat 返回 S_IFSOCK 的受控替身测试共享 scan_tree，抛 UnsafePathError；这不是实际 socket 平台验证。
2. 临时 failed、partial、running、completed 运行，分别以 20、5、20、20 天前时钟建立并按状态结束：14d 计划分别返回 ELIGIBLE、TOO_YOUNG、STALE_RUNNING、COMPLETED。结合源码和已有结束时间边界测试审阅；tmp 真实 mtime 量化限制见上。
3. 注入首个目标删除失败时，向该目标新增指向外部目录的真实 junction：结果 failed/partial 均为 a，b 继续成功删除；remaining 只列 a、a/file、a/link，不包含外部子项，哨兵保持 `safe`。另在删除 a 时修改 b，b 被重新判定 CHANGED_SINCE_PLAN 并保留修改，a 正常删除。
4. 独立注入首个发布前竞争：竞争文件 `competitor` 未覆盖，返回 ArtifactError；第二次发布注入失败时 ZIP 回滚、sidecar 不存在且源仍在；第二次发布前外部改写已发布 ZIP，返回 PARTIAL_ARCHIVE，保留 `changed`，拒绝回滚外部内容。
5. 真实 sidecar 重复 schema 键、schema=true、额外字段分别拒绝；合法 UTC archived_at 和 empty_directories 修改后 verify 通过。额外构造新 ZIP 成员并自洽重算 entries、content、archive 大小和 SHA，verify 通过，证实只验证内部一致性而非防篡改或可信来源。
6. 真实 CLI：默认 dry-run 0，独立快照记录路径、mode、mtime、文件字节相同；互斥参数 2；缺失 root 3；子进程注入 stage 校验失败 apply 返回 4；正常 apply/verify 均 0。源 run 目录在同一临时 root 内移名后仍能 verify，verify 前后快照相同。之前故障 method 99 和压缩流探针及真实普通文件 no-replace 见上。

限制：Linux 未动态验证；无恶意并发 TOCTOU 安全保证；验证无可信签名；socket 使用替身；未实际建立十万文件；文件系统实际 1ns 精度未验证。早先审查脚本遗留临时目录与自动策略拒绝清理的事实和原因仍如上记录，不影响产品结论；未操作真实 artifacts。最终 ACCEPT 仅为独立 G3，不代表 G5 或 Git 同步。
