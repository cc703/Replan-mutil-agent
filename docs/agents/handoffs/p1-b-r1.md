# P1-B-R1 实施交接（G2）

- 实施模型：gpt-6.1-terra / high / fork_turns=none；基线 `799ea56`。本包只改变组织，不声明业务修复；独立 G3 待审。
- `validate.py` 保持公开签名、文档和顶层类型错误，负责按固定顺序调用；`validation/index.py` 建立稳定索引并报告重复与键异常；`report.py` 收集并排序；`task_rules.py` 处理任务、期限和先后；`execution.py` 处理基准、快照及执行证据；`resources.py` 处理设备、人员、日历和运行窗口；`intervals.py` 保留领域无关重叠扫描。原 tasks 列表构造 frozen，保留重复 ID 行为，报告 task_ids 不做额外去重。
- 原测试按规则族迁到 `tests/unit/validation/`，共享纯构造在 `validation_helpers.py`。原收集和迁移后收集各 163 项，去路径后差集均 0，重复 0，162 passed/1 原 skip。原测试函数名及参数化 ID 保留。迁移时断言 AST 唯有 inventory 的跨模块名称存在性检查适配；后续按计划扩展原 AST 检查到所有内部模块、反向导入和环；两项 oracle 仅提取实例和计划构造到 helper，暴力 oracle 和断言保留，实例数仍 2049、3780，61 令牌清单保留。
- 差分：内存 `git show 799ea56:src/scheduler_core/validate.py`，以 `__package__=scheduler_core` 执行旧实现；pytest collection hook 用 spy 替换测试模块的 validate 绑定，每次比较完整 `model_dump_json()` 或异常类型及消息。共 6044 调用，6042 报告及 2 异常均一致，包括 5829 oracle 输入；162 passed/1 原 skip。构造 helper 和模块导入整理后已在最终树复跑同一差分，统计和结果相同；独立 G3 仍须自行验证。
- 检查：`uv run --python 3.11 --group dev python -m pytest tests -q -p no:cacheprovider`：162 passed、1 skipped（符号链接不可用）和 1 cache_dir 警告；`uv run --python 3.11 --group dev python tools/check.py`：布局、导入、原文、162 passed/1 skipped、ruff check、ruff format、strict mypy 全通过；单独 `tools/check_repo_layout.py` 与 `tools/verify_source.py` 均 PASS。迁移目录 Ruff 与 mypy PASS。`git diff --name-only` 另含 root 正在合法编辑的治理文件；专项未改这些文件、未提交或推送。
- 函数长度（行，AST `end_lineno-lineno+1`）：facade `validate` 46；index `build_index` 57；intervals `overlapping_pairs` 11；report `__init__` 2、`add` 20、`report` 10；execution `check_neighborhood` 29、`check_snapshot` 34、`check_end_changes` 62、`check_assignment_execution` 48；task_rules `check_deadlines` 43、`check_precedences` 30、`check_task_references` 15、`check_assignment` 31；resources `setup_rules` 15、`collect_occupancy` 58、`check_overlaps` 43、`check_calendar` 31、`check_running_blocks` 72。62 行的结束证据检查与 72 行的运行窗口绑定/扫描保留一个完整决策流程，避免仅为行数切分；均不超过 80 行。
- 文件行数：facade 67；index 78、intervals 14、report 44、execution 190、task_rules 135、resources 238、包 init 1。测试文件：api 126、blocks 113、execution 198、inventory 97、oracle 156、resources 159、rules 318、helper 147、init 0。测试中超过 60 行：AST/API 测试 66（原不变性检查加全模块导入图）、两组 oracle 73/71（保留独立枚举与断言）。
- 已知限制：未进行业务规则修复；独立审查应继续验证特殊坏模型、独立差分、函数职责及导入图。无新增依赖、无新业务行为；原文/工具/模型/上下文/fixture 未改。来源：本包 Claude 76 与 root G1、原始设计哈希清单及基线源码。

## G3 唯一结构项返工

按独立审查，容量事件扫描、窗口合并和二分、运行窗口跨组扫描已移到 `intervals.py`，只处理整数、字符串及区间元组，返回区间或标识符；人员和设备窗口共用合并与查询。领域判断和违规报告保留在 `resources.py`。无新增文件、框架或业务规则。

返工后 `intervals.py` 105 行（函数 `overlapping_pairs` 11、`merge_windows` 9、`overlapping_windows` 8、`overloaded_segments` 31、`cross_overlaps` 30）；`resources.py` 179 行（函数 15、49、18、24、47），此前行数记录为返工前快照。全部源码函数仍不超过 80 行。

最终 `uv run --python 3.11 --group dev python tools/check.py`：布局、导入、原文、162 passed/1 原有符号链接 skip、Ruff 检查与格式、mypy 均通过。最终树以 pytest collection spy 再执行完整旧版差分：6044 调用（6042 完整报告 JSON、2 异常类型及消息），全部一致，含 2049 和 3780 个 oracle 输入；162 passed、1 原 skip。等待独立复审，不宣称 G3 通过。
