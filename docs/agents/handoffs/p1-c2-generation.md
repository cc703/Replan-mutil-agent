# P1-C2 生成器切片交接

实际执行角色：`/root/p1c2_generation`，gpt-6.1-terra / high / fork_turns=none；来源为 root G1 与 temp v001，并非 Claude 输出。仅交接生成切片；G3、整体 G2/G5 与 Git 由 root 负责。

## 文件职责

- `generate.py` 入口与组装；`params.py` 参数、规模和前置校验；`rng.py` 固定索引 PCG64 子流；`workflow.py` 实验任务与属性；`dag.py` 层深和弱连通 DAG；`resources.py` 设备、人员与 setup；`timing.py` 容量、视野和窗口；`canonical.py` 规范 JSON；`integrity.py` 结构与画像检查；`__init__.py` 包标记。
- `tests/unit/generation/generation_oracle.py` 独立标准库容量与关键路径计算；`test_generate_{inputs,structure,factors,determinism,canonical,dag}.py` 覆盖对应入口；`__init__.py` 包标记。
- 子流按 `SeedSequence(seed, spawn_key=(index,))` + PCG64；此为规划中对子流的工程解释。输入归一化入口 `validate_inputs` 与 IO 协作使用。固定锚点上海 08:00，CLOSED 首窗 [144,288)。

## 执行与验收证据

| 条款 | 证据和状态 |
|---|---|
| 原文完整性 | PASS：`python tools/verify_source.py` 全部字节/行数/hash/批次通过。 |
| 输入与参数 | PASS：`test_generate_inputs.py` 覆盖输入类型、浮点非法值、概率域及端点、整数类型和上下界、三对倒置、类型映射、人数与极端配置；含 model_copy 重验证、次正规数。 |
| 规模与时间 | PASS：`test_generate_structure.py` 3规模×3利用率×3期限×5种子，独立容量、关键路径、H最小性、期限公式、技能、窗口和setup；`test_horizon_search_zero_and_limit` 覆盖上限和封闭时段。 |
| DAG | PASS：`test_generate_dag.py` 独立连接/最长路径检查及 3规模×6比例×10种子矩阵。 |
| 因素与随机性 | PASS：`test_generate_factors.py` 利用率、期限、深度、维护、hard level、技能双技能；`test_generate_determinism.py` 子流隔离、全局状态、AST禁用random/ortools，三组跨三个hashseed。 |
| 规范与完整性 | PASS：`test_generate_canonical.py` 各拒绝类别和结构画像代表性正反；详见下表。 |
| 静态与测试 | PASS：`$env:PYTHONPATH='src;.'; uv run --python 3.11 --group dev pytest tests/unit/generation -q` 408 passed（随后新增规范用例，定向 25 passed）；`uv run --python 3.11 --group dev mypy --explicit-package-bases tests/unit/generation` 8 files 通过；源码 mypy 10 files 通过；ruff check 与 format --check 通过。 |

三组规范字节 SHA-256，已由 `test_hashseed_all_scales` 分别在 PYTHONHASHSEED 0/1/2024 中对比；数字仅实施观测，未冻结黄金值：

| 参数 | SHA-256 |
|---|---|
| S, .8, .5, 0 | d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d |
| M, .6, .25, 1 | 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 |
| L, .95, .75, 2 | a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77 |

## R6 对照

| 拒绝项 | 定向证据 |
|---|---|
| 非 UTF-8、BOM、重复键、NaN/±Infinity、非对象、尾随垃圾 | `test_invalid_json`、`test_roundtrip_and_reject_noncanonical` |
| 缺失或额外换行 | `test_roundtrip_and_reject_noncanonical` |
| 集合重复和未排序 | `test_noncanonical_collection_and_axis`、`test_json_spelling_and_noncanonical_sets` |
| 整数槽 float/string | `test_noncanonical_json`、`test_noncanonical_collection_and_axis` |
| 非 UTC、微秒 | `test_noncanonical_collection_and_axis`、`test_integrity_rejects_mutated_models` |
| 空白、键顺序、Unicode转义、数值拼写 | `test_json_spelling_and_noncanonical_sets`；其他等价写法经重新序列化字节比较拒绝 |
| 空列表正例，非法引用/容量/重复边/环/人员 | `test_incomplete_lists_and_references`、`test_integrity_profile_rejections` |
| 画像规模、状态、now、事件类型、跨组、连通、时间 | 结构矩阵及 `test_integrity_profile_rejections`（规模通过正例，非法规模参数由入口校验） |

## 行数（Python `len(read_text(encoding="utf8").splitlines())`，含空行）

| 文件 | 行数 |
|---|---:|
| src/scheduler_core/generate.py | 58 |
| src/scheduler_core/generation/__init__.py | 1 |
| src/scheduler_core/generation/canonical.py | 54 |
| src/scheduler_core/generation/dag.py | 73 |
| src/scheduler_core/generation/integrity.py | 137 |
| src/scheduler_core/generation/params.py | 125 |
| src/scheduler_core/generation/resources.py | 62 |
| src/scheduler_core/generation/rng.py | 26 |
| src/scheduler_core/generation/timing.py | 135 |
| src/scheduler_core/generation/workflow.py | 72 |
| tests/unit/generation/__init__.py | 0 |
| tests/unit/generation/generation_oracle.py | 43 |
| tests/unit/generation/test_generate_canonical.py | 180 |
| tests/unit/generation/test_generate_dag.py | 58 |
| tests/unit/generation/test_generate_determinism.py | 70 |
| tests/unit/generation/test_generate_factors.py | 74 |
| tests/unit/generation/test_generate_inputs.py | 223 |
| tests/unit/generation/test_generate_structure.py | 54 |

本切片未运行最终整体 check；IO 作者与 root 负责整体验证。NumPy 许可、版本及 Linux 平台限制由 IO 交接说明。

## G3 REWORK：公开契约文档补正

依据 `p1-c2-review.md` P2，仅更新 generation 切片 docstring：公开入口、参数模型、输入校验、canonical、integrity 以及随机流、资源、DAG、workflow、timing 公开 helper。说明输入范围和前提、返回、异常、整数槽/UTC/上海锚点、IO 与修改行为；尤其 `assign_times` 会修改传入任务和人员并推进 RNG，编码器要求调用方提供完整性有效对象，未声称其自行校验。生成实例不保证求解可行或最优。未更改签名、行为或测试。

实际验证：`uv run --python 3.11 --group dev ruff format src/scheduler_core/generate.py src/scheduler_core/generation`：10 files unchanged；`ruff check` 同范围通过；`mypy` 同范围 10 files 通过；设置 `$env:PYTHONPATH='src;.'` 后 `uv run --python 3.11 --group dev pytest tests/unit/generation/test_generate_inputs.py tests/unit/generation/test_generate_canonical.py -q`：194 passed。未重复大型矩阵；等待原 G3 审查者定向复审。

## 收尾修正

实施模型 gpt-6.1-terra / high / fork_turns=none；状态：交独立 G3，未提交或推送。`assign_times` 深拷贝 tasks/persons，返回 `TimingResult(horizon, blocked, tasks, persons)`；调用方使用返回副本。RNG 仍原样消费。groups 保存任务 ID 字符串，edges 保存 pred/succ ID，无任务对象引用，故不需映射。新增 1 个集成测试：真实调用路径检查输入深快照、两次同状态 RNG 的结果和状态、任务人员及可变容器非别名（含预置 blocked 元素）、输出变化、参数不变和规范字节一致。测试文件 135 行。只读审计 generation 其余模块与 generate：未发现对业务入参的原地修改；RNG 推进为显式消费，局部集合/模型转储的修改不改变输入。

三组 S/M/L 哈希按顺序，PYTHONHASHSEED=0、1、2024 各次实测均为：

```text
0    d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
1    d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
2024 d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
```

验证：`uv run --python 3.11 --group dev python -m pytest tests/unit/generation -q -p no:cacheprovider` 410 passed, 1 warning（禁用 cache provider 时未知 cache_dir）；`python -m ruff check src tests` All checks passed；`python -m ruff format --check src tests` 63 files already formatted。以上 python 均经相同 uv 前缀运行。原计划 mypy 命令因 `generation.generation_oracle` 与 `tests.unit.generation.generation_oracle` 重复模块名失败；加 `--explicit-package-bases` 后 18 source files 通过。`git diff --check` 退出 0，仅有 README、model-policy、dependency-register 行尾警告。

`uv run --python 3.11 --group dev python tools/check.py` 执行一次：Layout、Imports、verify_source 全 PASS；718 passed、1 skipped（Windows symlink unavailable）；ruff All checks passed；67 files already formatted；mypy 67 source files 成功。全量 check 后补一条 release 实际变化断言，单文件测试重跑 6 passed、1 warning；无生产代码变化。首次哈希命令缺 PYTHONPATH 导致 ModuleNotFoundError；设置 PYTHONPATH=src 后得到以上 9 个结果。root 独立计算 135 样本汇总与修前一致：2e976fbbb2358436b516b434d52b90dd065282bc221a30fc9f4564824b2aae9e。
