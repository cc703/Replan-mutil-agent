# P5 核心实施交接

来源：`docs/work-packages/p5.md`、`p5-claude-plan.v001.md` 与 root 本次派发；实际作者 gpt-6.1-terra / high / fork_turns=none。状态：提交独立 G3 审查，不代表验收；未提交或推送。

实现：`diagnose.py` 提供详细与简版诊断；`diagnostics/groups.py`、`inputs.py`、`core_search.py` 分别提供目录、证据与删除过滤；初排和重排各自原构造增加可选分组重建钩子，默认参数沿原路径。两模型对截止组使用真实假设文字，假设核加入全部未假设组后重新求解证明，无证明则回退全部组。`relax.py` 与 `diagnostics/relax_model.py` 求解权重乘延后槽数，排除可比较支持集，对原实例和假设副本分别验证。假设提案不自动采用；授权按现有计划 ID 过滤，不创建或改绑授权。

验证记录：
- `uv run --python 3.11 --group dev python -m pytest tests/unit/diagnostics tests/unit/test_initial_search.py tests/unit/test_solve_initial_oracle.py tests/unit/test_p4_impact.py tests/unit/test_p4_oracle.py tests/unit/test_p4_objective.py -q -p no:cacheprovider`：108 passed；后续新增无关组与守卫测试，单文件 6 passed。pytest 存在既有 cache_dir 配置警告。
- 独立枚举微例验证设备容量与两个截止冲突的核不可满足、删除任一组可行；两任务松弛微例验证两个不相容支持集、精确权重代价与双校验。
- 从 Git 基线 `681f34de0a3a776afea894b3b7d1acef0f2eeaf0` 在系统临时目录加载原模型，各 3 个单线程初排/重排微例比较状态、目标及独立校验，全部通过；不是大规模差分。
- 已安装 OR-Tools 9.15.6755 实测固定及可选固定区间：NoOverlap 和 Cumulative 的 OnlyEnforceIf 禁用为 OPTIMAL、启用为 INFEASIBLE；AddAssumption 冲突返回 [0]。当前删除过滤以重建组实现，假设文字用于截止组，资源为补齐固定组。
- `tools/check_repo_layout.py`、`tools/verify_source.py`、`git diff --check` 通过；定向 ruff check 及 mypy `--explicit-package-bases` 通过；format 中一次发现 test_relax.py 未格式化，已修复，需末次复核。

限制与审查重点：资源/人员/冻结与窗口多冲突的独立 oracle、极端预算、上下文授权及运行事实组合仍需独立 G3 探针；本交接不声称覆盖全部组合或硬实时。模型构造和验证可能越过墙钟预算，超时后不再启动后续求解。总代价以 Fraction 精确缩放求解，公开 cost 为现有 float 契约。未执行全仓 check，由 root 执行。

## G3 REWORK2/3（定向返工）

- `replanning/model.py` 在构造完成后计算剩余预算；小于等于零时直接返回 UNKNOWN，未创建或调用求解器。模拟时钟在建模后恰好耗尽，solver spy 验证零调用与返回字段。
- `relax.py` 在判断空冲突早退前统一通过 `diagnostics.inputs.prepare` 验证与派生输入，删除重复的冻结/free 检查。测试覆盖缺失 snapshot、过去开始任务不得释放以及有效输入的空核返回。
- `uv run --python 3.11 --group dev python -m pytest tests/unit/diagnostics/test_diagnose_cases.py tests/unit/diagnostics/test_relax.py tests/unit/diagnostics/test_relax_oracle.py tests/unit/test_p4_impact.py -q -p no:cacheprovider`：37 passed；pytest 既有 cache_dir 警告一条。
- 对两个源码文件及两个测试文件运行定向 ruff check、ruff format --check、mypy --explicit-package-bases：通过；首次 mypy 检测 spy 返回类型标注有误，修正后通过。`git diff --check` 通过，仅提示现有 CRLF 转换警告。

## G3 REWORK4（冻结组单调性）

`replanning/model.py` 对 RUNNING/DONE 始终从执行快照计算已观察/预计工期；移除 frozen 组时仅解除固定时间和资源绑定，工期维持该观察值。默认冻结路径仍使用同一观察工期和固定端点。新增提前完成（名义 4、观察 2）和运行超时（名义 2、预计 5）反例：分别核验移除冻结前后可行及实际工期、移除冻结后的可行性和工期，并核验后者返回 `deadline:X` 与 `frozen:X` 的不可约核。

`uv run --python 3.11 --group dev python -m pytest tests/unit/diagnostics/test_groups.py tests/unit/diagnostics/test_core_search.py tests/unit/test_p4_impact.py -q -p no:cacheprovider`：32 passed，既有 pytest cache_dir 警告一条。针对模型与该测试的 ruff check、format --check、mypy --explicit-package-bases 通过；`git diff --check` 通过，现有 CRLF 提示。未运行全仓检查。
