# P1-A 独立 G3 审查记录

2026-11-09，派发配置 gpt-6.1-terra / high / fork none；未参与本包实施。G2 增补和最终审查仍待交付，以下为主体预审，不是最终结论。

## 主体预审

- 以 Python AST 提取规格第 3 节 21 类字段名，与 Pydantic `model_fields` 逐类比对：无原字段缺失；新增仅 Task.required_skills/requires_person、Instance.persons、Assignment.person_id。Person、PersonBlockedWindow 与 Slot/Event 另查。原始字段默认值及原始模型定义仍需以完整 G3 的逐项核对为准。
- 实际执行 `python tools/verify_source.py`，三份原文及 14 批全部 PASS；`uv lock --check` 成功。`uv run --no-sync` 读取安装元数据：pydantic 2.14.3 MIT，pydantic-core 2.50.4 MIT，annotated-types 0.8.0 MIT，typing-inspection 0.4.5 MIT，typing-extensions 4.16.0 PSF-2.0；pydantic 的强制 core 精确版本一致。numpy、hypothesis、ortools 未安装。首次自行检查分发名时未规范化下划线导致 core 和 typing-extensions 被误报为未安装，随即改用 importlib.metadata.version 直接查询，以上为纠正后的结果。
- 预审发现：`src/scheduler_core/axis.py:44` 接受 `TimeAxis(t0=datetime(9999,12,31,23,59,tzinfo=timezone.utc),horizon_slots=1)`，但 `to_dt(1)` 抛 OverflowError，虽 1 为规定允许的 horizon 端点。应规定并测试不可表示的轴边界，建议构造时拒绝超出 datetime 表示范围的端点，以保证已接受轴的双向转换。
- `docs/engineering/dependency-register.md` P1-A 条目只列版本/metadata 与通用 PyPI，未覆盖该文自身所列新条目所需的具体官方源码许可证链接、替代与许可/NOTICE 范围等；建议核实并补充，未核实项如实标注。
- `tools/check.py` 初版 mypy 只覆盖 tests/unit 而非所有 tests；总设计师已通过 Claude G1 派发有限增补，须待 G2 后复核全量 tools、tests、src 及原治理测试语义。README 的阶段表述已修正。

本阶段尚未复跑最终 check.py、全量测试或安装 API 探针，未审查作者会话。下一步等待增补 G2，定向复查改动和执行完整 G3。

## 最终 P1-A 工程 G3 — ACCEPT（2026-11-09）

预审三项均已关闭：

1. **TimeAxis 溢出 CLOSED**：`axis.py` 在 UTC 归一化与轴构造时检查可表示范围，超界作为验证错误；查询 datetime 转换超界为 ValueError。独立探针确认最大附近有效端点双向往返，原 `9999-12-31 23:59 UTC` 加一个槽被构造时拒绝；作者增加极端边界测试。本人第一次探针误以 23:55 加 5 分钟仍在同一天，实际运行产生预期的构造错误；改为 23:54:59 后往返通过，不把第一次失败隐去。
2. **依赖登记 CLOSED**：逐包记录版本、用途、依赖关系、固定官方元数据与源码许可、替代方案和发行复核范围。独立读取五个安装包元数据；固定源码许可链接经官方 GitHub/raw 核查，typing-inspection 的 raw 请求超时，GitHub 固定页面可读；完整发行包与 NOTICE 未审计，登记已明确分发前处理。
3. **治理类型增补 CLOSED**：`tests/governance/test_verify_source.py` 的 SourceManifest/SourceEntry/BatchEntry 与 fixture 各字段类型一致；原 `dict(b, start=1, end=2)` 保留，cast 不改变运行值；`test_gates.py` 对异构字典使用 object 与局部 cast。对照 baseline diff 未改断言、测试输入或 skip，未新增 ignore/noqa/Any。最新 cast 修订后独立重跑该文件及全量 mypy/ruff，结果见下。

模型审查：原规范第 3 节 21 类字段与默认值已对照，AST 字段比对无缺失；新增 Task 两字段、Instance.persons、Assignment.person_id 及 Person/PersonBlockedWindow 与本包范围一致。Slot 严格整数、Event 判别联合、原 ReplanParams.num_workers=8 与 Violation 代码集合保持。人员空 ID/空技能拒绝，空阻塞默认；旧 JSON 与容器隔离有实际断言。独立探针验证需人员无 persons、未知人员和不可能期限可构造，模型没有代替未来独立校验器；当前未实现求解器、V1–V11 或三个后续数据来源。TimeAxis 原方法签名、UTC 整数 timedelta、范围与异常覆盖已审查。已安装 API 探针通过 ConfigDict、Field、strict、field/model validators、model_validate_json、TypeAdapter；Event 判别单独通过。

检查入口将布局、导入边界、原文、全部 tests、tools/tests/src 的 ruff 格式和 mypy 纳入；相对基线未改布局或导入规则。共享树 root 的 AGENTS、ADR、进度及派发更新按授权与作者交付区分；源码/测试、pyproject、锁、依赖表及 README 属已授权范围，治理两文件为 Claude/G1 增补；原文未改。

实际验证：

- `uv run --no-sync python tools/check.py`，设置 `PYTEST_ADDOPTS=-p no:cacheprovider`、`PYTHONDONTWRITEBYTECODE=1` 与缓存目录 `artifacts/tmp/`：62 passed、1 skipped（symlinks unavailable），Layout/Imports/source PASS，ruff PASS、11 files already formatted、全量 mypy 11 source files 无问题；退出 0。该次在治理测试最后 cast 补充前运行，补充仅限对应测试类型收窄。
- cast 补充后 `uv run --no-sync python -m pytest -q -p no:cacheprovider tests/governance/test_verify_source.py`：10 passed、1 skipped、1 warning（禁用 cacheprovider 导致配置 cache_dir 未知）；全量 `uv run --no-sync python -m mypy --explicit-package-bases tools tests src`、ruff check 与 format 检查均通过。作者交接另报告最终完整入口 62 passed/1 skipped；不将其结果当本人复跑。
- `uv lock --check` 通过；元数据与固定锁一致；numpy、hypothesis、ortools 未安装。本次不安装额外依赖或复制代码。

实际范围限数据模型和时间轴；ACCEPT 不声称独立业务校验、求解、模拟、后续三项数据来源或远程同步已完成。独立 G3 可交总设计师集成；许可证完整发行审计及本机符号链接权限限制如上。
