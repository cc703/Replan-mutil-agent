# P1-C3 cleanup / shared 实际派发 v001

模型gpt-6.1-terra；reasoning_effort=high；fork_turns=none。角色storage-steward实施专项。仓库D:/Default/Replan-mutil agent，无旧会话上下文。

用户授权继续原顺序P1，Claude额度不足即temp代规划。C2已G3/G5 ACCEPTED，基线HEAD43b19a42b853fa89878b5f08ab930b4c427c71c3，721 passed/1原symlink权限skip、68文件静态PASS。当前root治理文档改动属root，不覆盖、不提交。当前P1-C3清理/归档包，temp v001完整方案经root G1 PASS（卡片末最终复核），不做P2/前后端/make_report，B1/solver决策保留延期。

必先读AGENTS、PROGRESS、RESUME、model-policy、storage-steward角色、公共前言及common-delta（历史与当前冲突以当前用户/AGENTS/本包授权为准），coding-standards/file-storage-standard/open-source-policy/review-gates/git-workflow。先python tools/verify_source.py。全文读docs/work-packages/p1-c3-temp-plan.v001.md（冻结完整契约/测试清单/两个prompt）、p1-c3.md末root G1。Claude初版仅历史来源，不需自己拼冲突契约。读实际io/artifacts/manifest/paths/errors/cache_publish及既有AST/tests/Makefile和检查工具。新标准库API以已装3.11源码/签名/临时探针核实。

你的唯一写入集合：
src/scheduler_core/io/artifacts.py（仅增加open_existing及maintenance方法，不改现有行为）
src/scheduler_core/io/maintenance.py
src/scheduler_core/io/tree_snapshot.py
src/scheduler_core/io/retention.py
src/scheduler_core/io/index_refs.py
src/scheduler_core/io/removal.py
tools/clean_artifacts.py
tests/unit/io/maintenance_fixtures.py
tests/unit/io/test_maintenance.py
tests/unit/io/test_tree_snapshot.py
tests/unit/io/test_cleanup_policy.py
tests/unit/io/test_cleanup_references.py
tests/unit/io/test_cleanup_apply.py
tests/unit/tools/test_clean_artifacts_cli.py
Makefile（仅clean-tmp默认dry-run薄委托）
README.md（清理/维护短用法；归档章节root后续集成）
docs/engineering/file-storage-standard.md（仅补清理操作/限制说明，规则含义不改）
docs/agents/handoffs/p1-c3.md
禁止其他写入。不新建tests/unit/io/__init__.py，不改路径/布局/依赖/锁/旧测试/原文/模型校验生成器/C1C2旧行为。测试helper若导入有困难可按temp计划复制少量fixture到已授权测试并移除自己未发布helper，不扩文件。若必须新增职责文件先报告root，不擅自扩大。

范围：实现temp计划全部共享入口/安全树快照/类型化结果/API、只读retention和INDEX解析、apply删除、clean CLI；archive系列由下一作者负责，不写其文件。maintenance中归档方法可延迟导入归档方的实现，接口先与root/归档方明确；不要保留NotImplemented等虚假完成。请先实现并固定公共TreeSnapshot/扫描函数/维护结果与入口API，给root发送精确签名及字段约定后停止改这些公共签名；root将据此启动归档作者，共享文件仍只归你维护。其后继续清理，必要接口协商由root和两作者协调，不相互覆盖。shared/cleanup本切片通过不等于总C3完成。

完整行为和验收严格依temp v001及root G1，尤其：dry-run一字节不写不创建root；ArtifactStore.open_existing检查原链和存在性再绑定；所有对象重新从绑定store推导，伪造plan不可越界；tmp递归最新mtime整数ns，failed/partial ended_at且14d下限；running/complete/引用保护不删；INDEX不可读/截断/歧义fail-closed；守卫拒junction/hardlink/特殊文件。安全删除自底向上且manifest最后，不rmtree/不跨shell/不改目标外权限；重验变化跳过，部分失败报告剩余，其他候选继续。测试必须实质正反值断言，含真实Windowsjunction与只读目标、不新增skip/xfail，不用不真实的“全部防篡改”承诺。

只在tmp_path或系统临时构造数据执行apply；不得触碰真实artifacts。函数/模块保持简单清楚，大小仅审查参考不压缩排版。完整类型/docstring，不引新依赖，不提交/推送/改Git。

先做源码/Windows readonly unlink等已装API探针，读原测试。定向新增测试与必要静态先过，归档作者到位后再联合跑完整check一次；若其未到位产生缺失导入须如实交接而不伪称G2 PASS。最终root会完整集成和独立G3。命令：uv run --python 3.11 --group dev python -m pytest 对应新增测试 -q；ruff check/format --check、mypy对应文件；uv run --python 3.11 --group dev python tools/check.py；git diff --check。使用-p no:cacheprovider会有既有cache_dir警告可披露，不改配置掩盖。失败做范围内修复；范围变化报告。

交接到指定handoff：各文件用途、精确API和模块职责、每项必要边界测试与真实命令结果、平台实测、无TOCTOU/只读非防篡改/Linux未动态测等限制、旧断言未变、实际派发模型参数。DONE只是切片交付，不是独立G3/G5。
