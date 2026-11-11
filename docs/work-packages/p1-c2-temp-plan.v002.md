# P1-C2 temp 计划 v002：缓存职责位置增量（待 G1）

在 v001、Claude 初版和 Δ 之上仅替换缓存编排模块位置；其余契约、测试、门禁均保留。本增量由 temp planner 提出，不代表 Claude；待 root G1 审定后派发。

## 依据与决定

现有 `tests/unit/io/test_artifact_layout_rules.py::test_storage_has_no_forbidden_imports` 对 `src/scheduler_core/io/*.py` 作 AST 扫描，禁止直接导入 numpy、models、validate 等；目前 `io/instance_cache.py` 的 numpy 与 `scheduler_core.models.Instance` 导入触发既有断言。该文件承担生成器、领域模型与存储之间的编排，不是通用存储基础设施。迁至 `src/scheduler_core/instance_cache.py`，`io/cache_area.py`、`ArtifactStore` 与发布机制保持通用存储职责；不在 generation 下加入 IO，不使用重导出、动态或相对导入来规避测试，不创建兼容 wrapper。原路径尚未发布，直接删除。

## 实施增量（可直接派发）

在原实施 prompt 和 v001 约束不变的前提下，精确调整本次授权路径：将 `src/scheduler_core/io/instance_cache.py` 移为 `src/scheduler_core/instance_cache.py`；移除旧路径，只修改新模块所需的导入路径，`ArtifactStore`、`ArtifactError` 与 `UnsafePathError` 从 `scheduler_core.io` 下各自定义模块显式导入。公开导入为 `from scheduler_core.instance_cache import InstanceCache`；`CacheResult`、`CacheConflictError` 及调用签名、输入输出、异常、缓存 key、字节、版本、读写与并发行为不变。更新当前新增的 `tests/unit/io/test_instance_cache.py` 中全部相关导入和 importlib 字符串（含 `_params_hash`、`_float_token`），保留全部现有断言；更新 `README.md` 新用法显示新公开导入。不得改既有 C1 测试、删除测试、降级断言或增加 skip/xfail。依旧只通过 ArtifactStore/CacheArea 操作存储；不改缓存规则、不修改 generation 的纯函数边界、不做兼容导出。

本增量专项精确写入仅为 `src/scheduler_core/instance_cache.py`（新建）、`src/scheduler_core/io/instance_cache.py`（删除未发布新增文件）、`tests/unit/io/test_instance_cache.py`（仅调整导入引用）、`README.md`（仅缓存示例导入），以及实施交接 `docs/agents/handoffs/p1-c2.md`（记录改动与证据）；后续其他已分配工作仍受 v001 范围控制。原主 prompt 文件由 root 管理，本专项不得修改它、进度、其他 agent 的工作或 Git。若出现超范围需求先向 root 报告。root 可指派原 IO 作者接管顶层路径。

运行原失败测试、缓存定向测试与 `uv run --python 3.11 --group dev python tools/check.py` 全量；如实报告实际结果，要求既有 250 passed 基线和新增测试全部通过，原有 1 个 symlink 权限 skip 仅按基线记录，新增 skip/xfail 禁止；不得将测试总数机械固定，既有断言完整保留。核对 rg 无旧导入及 wrapper（含文档、测试及业务代码）；若历史规划文件仍保留旧路径则报告其历史属性，由 root 单独维护。对照调整前后的现有缓存测试断言和行为，确认未引入语义变化。

## 独立 G3 增量

除原 G3 要求外，核对最终 diff：顶层编排直接使用领域依赖，底层 io 无禁止导入或重导出、无绕过；原路径已删，调用方及 README 使用新路径，无不必要的兼容层；既有断言未变且无新增 skip。独立运行失败测试、缓存测试及完整检查，检查输出并记录已通过项目基线与新增测试、原有 skip、命令及平台限制。核对 key、canonical 字节、结果/异常、并发与清理语义未因移动改变。结论使用 ACCEPT / REWORK / ESCALATE。
