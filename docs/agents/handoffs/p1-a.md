
## 实施交接（2026-11-09）

- 模型：gpt-6.1-terra，high，fork none。起点 452b2be，分支 codex/p0-governance；已有共享治理改动未触碰。
- 三个源码文件提供原模型、Event/Slot、人员扩展和 TimeAxis；两项单元测试、src 查找配置及检查入口；仅引入 pydantic 2.14.3，pydantic-core 2.50.4，及锁定传递依赖。新增目录 src/scheduler_core、tests/unit。
- 实测 API 探针通过 ConfigDict、field_validator、model_validator、Field 约束/判别器、严格整数、model_validate_json、TypeAdapter；许可证从安装元数据记录于 dependency-register。
- 模型基础约束包含整数槽、正工期/容量/需求、区间、非负有限指标、唯一 ID、先后引用、分配键。设备与人员兼容、人员缺失、不可行截止和环留独立 validator；空人员日历无阻塞。Person id 与技能不得为空；extra 禁止。未修改 ReplanParams 原始默认值及其原 int 类型。
- 三个数据来源有意缺席：RUNNING new_end 持久来源、冻结 end 对 V11 的证据、NEGOTIABLE 放宽凭证。无业务校验器，未将缺失证据判为通过。V1–V11、求解器、生成器均未实现。
- `uv lock --check`、`uv sync`、版本核验、`uv run python tools/check.py`、布局和原文核验通过；pytest 61 passed、1 skipped（无法创建符号链接）；`-p no:cacheprovider` 下 pytest 对原有 cache_dir 配置产生一条警告。原始 mypy 检查范围后经 Claude 增补扩展至 tools、tests、src，治理测试类型问题已修复，详见下节。
- G2 自检：原始模型默认值与导出、代表性可变容器隔离、双进程导入顺序、时间轴边界、事件判别及职责边界均有断言。待独立 G3 审查。

补充：原模型默认值回归表、代表性容器隔离、双进程导入顺序、时间轴边界、三种事件及所有指标非法值测试已加入；最终完整检查 61 passed、1 skipped，ruff/mypy 通过。


## 全量 mypy 范围增补（G2）

- 配置 gpt-6.1-terra / high / fork none。增补前 `uv run mypy --explicit-package-bases tools tests src` 共六错，仅在两份既存治理测试：`test_verify_source.py:101` 缺少 dict 类型参数；`test_gates.py:109` 异构 outputs 赋值类型冲突，117、120 各有索引目标及 setitem 重载错误。增补后同命令 11 个源文件零错。裸 `uv run mypy tools tests src` 会把 verify_source 识别为两个模块而失败，故使用 G1 明确允许的 `--explicit-package-bases`，未排除文件或放宽配置。
- `test_verify_source.py` 的 change 参数补充对应嵌套字典/列表类型；`test_gates.py` 中 manifest 标为 `dict[str, object]` 以容纳故意畸形的 outputs；两处 cast 将已知的 git 字典收窄以允许原有两次 commit 赋值。cast 不改变运行值；无新增 ignore、noqa 或 Any。原业务测试中既有 type ignore 用于有意传入错误类型，并非本次新增。
- 增补前 `uv run python -m pytest --collect-only -q` 62 项，既存完整运行 61 passed、1 skipped；增补后完整 check 同为 61 passed、1 skipped，治理两文件收集 34 项与此前列表一致。跳过项仍为符号链接不可用。增补前误用 `uv run pytest --collect-only -q` 导致 tools 找不到并收集失败，正确 `python -m pytest` 入口重跑成功。
- `uv run python tools/check.py` 全部通过（含 tools、tests、src 的 ruff、format、mypy，以及布局、导入边界、原文和全部测试）；`uv run python -m pytest tests -q -p no:cacheprovider` 61 passed、1 skipped，因原配置 cache_dir 有一条警告；单独布局与原文核验通过。测试输入、断言、测试数量、skip 和调用顺序未变；增补未修改 src 或 tests/unit。


## G3 预审修复（在类型增补独立完成之后）

- 恢复原 P1-A 范围后修复 TimeAxis：构造时验证 UTC 终点可用 datetime 表示；UTC 归一化或计算超界转为清晰验证错误，查询 datetime 归一化超界转 ValueError。测试先重现原端点溢出失败，再覆盖最大可表示端点往返、越界终点、极大槽积、最小/最大日期时区溢出和查询时溢出；未修改业务默认值。
- 依赖表改为中文逐包登记，固定版本 PyPI 与源码许可、直接/传递关系、用途、替代和许可义务；记录元数据与 API 探针的实际范围，发行包与 NOTICE 未逐项审计，分发前须复核。
- 最终 `uv run python tools/check.py` 通过：62 passed、1 skipped，ruff、格式、全量 mypy（tools/tests/src）、布局、依赖边界、原文均通过；`uv run python -m pytest tests -q -p no:cacheprovider` 同为 62 passed、1 skipped、原有 cache_dir 警告；`uv lock --check` 和全量 mypy 单独复跑通过。跳过仍为符号链接不可用。可进入最终独立 G3。

## 治理测试注解复审修正

此前嵌套 dict 注解错误地把其他元数据都视为列表/整数；现以 `SourceManifest`、`SourceEntry`、`BatchEntry` TypedDict 描述 fixture 的完整键与值类型。原 `dict(b, start=1, end=2)` 保留，外层 cast 仅补充 mypy 无法推断的 TypedDict 返回类型，运行时值及调用顺序不变。无测试输入、断言或 skip 变化。首次类型复核暴露 dict 构造返回普通 dict 的错误，加入该 cast 后完整 `uv run python tools/check.py` 通过：62 passed、1 skipped；全量 mypy、ruff、布局、导入边界及原文校验通过。
