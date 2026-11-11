# Temp planner 交接

实际角色 temp planner / prompt engineer，gpt-6.1-terra，high，fork_turns=none；用户明确授权暂代 Claude，额度恢复后交回；不冒称 Claude。原方案来源 p1-c2-claude-initial.md 与 p1-c2-claude-delta.md，补充计划 p1-c2-temp-plan.v001.md；均待 root G1。原文 `python tools/verify_source.py` 本次全部通过。补充 binary64 缓存全域编码、H 零容量和上限、平台 no-replace 失败关闭、参数深层不可变和完整性、上海本地日历与 UTC 换算、语义 hash 与配置 hash 区分。依赖实际 API、wheel、许可、现有 mypy 兼容及原子原语尚未核实，列为实施前置；root 的候选版本资料不等于通过。未实施、未安装、未提交。Claude 恢复时应读取本交接、temp 计划、初版与 Δ，审视上述工程决定及后续实际实施交接，不能将 temp 输出写成 Claude 批准。


G1 修订：补齐 dag、cache_area 测试范围，独立 cache_publish 与测试，仅 Windows/Linux 原语并本机动态验证、其他平台失败关闭；G3 结论 ACCEPT/REWORK/ESCALATE；缓存最长 116 字符；不增加 tests/unit/io/__init__.py。上海本地 20–08 由 root 审定，保留 00Z 锚点。实施 prompt 独立持久化。


V002 待 root G1：C1 的 IO AST 边界禁止 numpy/models，建议将实例缓存编排从 io 移到 scheduler_core.instance_cache，删除未发布原模块，不做 wrapper，保持缓存语义及既有测试；精确实施与独立审查增量见 p1-c2-temp-plan.v002.md。未改实现、旧计划或主 prompt。
