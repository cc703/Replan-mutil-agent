# P1-C2 独立 G3 审查（未完成）

状态：IN-PROGRESS，结论 PENDING；此前 ESCALATE 为覆盖不足的中间状态，已撤回。实际角色 gpt-6.1-terra/high/fork_turns=none。不得根据本记录冻结黄金哈希或通过 G3。

已独立执行：`python tools/verify_source.py` 全 PASS；设置 `PYTEST_ADDOPTS=-p no:cacheprovider` 且 Ruff/mypy 缓存位于系统临时目录下运行 `uv run --python 3.11 --group dev python tools/check.py`，退出 0，717 passed、1 既有 symlink 权限 skip；layout/import/source、ruff、format、mypy 67 文件 PASS。单独跨进程将 PYTHONHASHSEED 设为 0、1、2024，分别生成并计算 canonical SHA-256，三个进程一致：

- S, 0.8, 0.5, 0: d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d
- M, 0.6, 0.25, 1: 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5
- L, 0.95, 0.75, 2: a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77

尚未完成要求的独立矩阵 oracle、所有规范和缓存反例、Windows 原语探针、完整文件及规范逐条审阅、官方来源独立复核。Linux 未动态验证；不能声称 TOCTOU 防护。NumPy Windows wheel 捆绑 GCC runtime 及例外，授权范围见 ADR0007，不应简化为纯 BSD。已有测试通过及作者交接不能代替这些步骤。需要继续独立 G3 后再给最终结论。


## G3 本轮正式结论：REWORK

唯一发现 P2（工程契约文档缺失）：`src/scheduler_core/instance_cache.py:88` 的公开 `get_or_generate` 无 docstring；`src/scheduler_core/generate.py:15`、`src/scheduler_core/generation/canonical.py:21`、`src/scheduler_core/io/generator_config.py:40`、`src/scheduler_core/io/cache_area.py:26` 等本包公开函数仅有概述，未完整说明输入/范围、返回、时间单位、异常和副作用。与 `docs/engineering/coding-standards.md` 公共函数文档要求不符。建议两原作者按职责补齐本包公开 API 的适用契约说明，必要时说明无副作用、已定义错误、5 分钟槽和读写缓存行为；不得改变业务行为。未发现其他需返工的实质问题。此前覆盖不足产生的 ESCALATE 已撤回，不是外部阻塞。

## 独立检查补充记录

- 在系统临时目录 p1c2_review_oracle.py 自写标准库 oracle，`uv run --python 3.11 python` 执行：135 组 3 scale × 3 u × 3 tau × 5 seed，另 180 组 3 scale × 6 depth ratio × 10 seed 均 PASS。独立验证规模、引用、人员技能 AND、DAG 拓扑/弱连通/层深/跨组、CP、Fraction W/C 和 H 最小性/CP clamp、release 限界、deadline 公式、当地 CLOSED 窗、setup 与其他窗口。release 的随机值按范围检查，未独立重放其子流。
- 系统临时目录 p1c2_cache_review.py Windows Python 3.11：10007 个 binary64 采样和边界、负零、语义参数 hash、最大 key 116、非法 flag、元数据及自洽实例篡改/重生成、文件/空非空目标不覆盖、注入发布失败后清理重试、真实 junction 与双进程竞争 PASS。只能证明本机文件系统；Linux 未动态测试，不声称抵抗恶意并发路径替换 TOCTOU。另独立对合法实例变异的 15 种 canonical 与 7 种 YAML 反例及原始字节 hash PASS。
- 检查 H_MAX=1000000 恰好满足、超过上限、空设备零容量、不可满足的小上限、参数深层冻结与外部字典隔离、极端有效参数、非法非有限值和 deadline 因素隔离：PASS。第一次手算容量预期错误而失败，纠正为精确容量 500032 后重跑通过；没有改业务代码。
- `uv lock --check` PASS。官方 PyPI JSON 下载 Windows cp311 wheel 到内存并核对 SHA256 和许可证：NumPy 2.4.6 `1e254a00cdf42b1e4d5b3d68d33af63268d41340d8885df2ab6470f2e1500147`；PyYAML 6.0.3 `9f3bfb4965eb874431221a3ff3fdcddc7e74e3b07799e0e84ca4a0f867d449bf`；types-PyYAML 6.0.12.20261103 `444654c61f635dab82c092a511aa96a0ce31164810784b9a37314e3e56532ac8`；本机安装版本一致。wheel 实读 NumPy/OpenBLAS/LAPACK 与 GCC runtime exception，用户已按 ADR0007 授权开发/运行，未来二进制分发另审；PyYAML MIT 与 types-PyYAML Apache 2.0 文本核对。首次误以为 PyYAML LICENSE 必须含 MIT License 标题的断言失败，已改为读条文；随后首次输出时 Windows GBK 无法编码作者名，设 UTF-8 输出后成功。NumPy 官方随机 API https://numpy.org/doc/2.4/reference/random/parallel.html 与 https://numpy.org/doc/2.4/reference/random/generator.html ；Windows 原语 https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw 。完整 check 中 mypy 67 文件 PASS。
- 检查源码未发现 random/ortools 或动态导入绕过；动态 importlib 命中仅测试用。旧 models、axis、已有布局断言未变；现有 yaml 边界仅为 generator_config 精准例外。历史旧缓存路径系旧计划，不作现行接口缺陷。`git diff --check` PASS，Git 仅报告工作副本 CRLF 转换提示。未修改受审源码或测试，未提交、推送。
- 复审要求：作者仅补文档后定向核对实际 API 契约并运行适当静态/回归检查；无需重复已完成的 135/180/10007 扫描。最终是否 ACCEPT 及根回归哈希冻结待复审。

## 收尾独立 G3 最终复审：ACCEPT（2026-11-11）

独立恢复 reviewer：gpt-6.1-terra / high / fork_turns=none；未参加实施或规划，不假称旧 reviewer 会话仍在运行。复审 Claude 消息86 收尾清单、历史 G1/temp 计划及两份 C2 交接；`python tools/verify_source.py` 全 PASS。前次正式 G3 唯一 REWORK 的公开 API 文档已补：检查生成、规范编码、缓存与配置 IO 的公开契约、异常和副作用以及 README 用法；本次 `assign_times` 文档与 `TimingResult` 及 RNG 消费一致，无当前原地修改描述。历史交接中旧行为描述是历史记录。

独立系统临时目录探针按实际 generate 路径构造真实对象，预置人员 blocked 窗口，absence/hard 均设1。输入深快照、任务/人员与其可变容器及预置窗口非别名、顺序、release/deadline/level 和缺勤确有变化、groups/edges 为 ID 且未变、两次相同初态 RNG 的结果与最终状态均 PASS。读当前计算路径确认拷贝发生于抽取前，RNG 仍显式消费；generation 其余模块赋值和集合修改是局部对象或转储，未发现其他业务入参原地修改。新增测试含深快照、非别名、实际变化及集成断言，无新增 skip/xfail 或黄金常量；文件为追加式结构。无发现需返工项。

独立三进程实际 SHA256（每行依次 S/.8/.5/0、M/.6/.25/1、L/.95/.75/2）：

```text
0    d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
1    d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
2024 d0e16c15f5b841ec6b0b1d00219d25b70164d0c58fccb8579f5845bf7b09869d 712e9aebfca29641f62a63d9152d67af1f7562bdcc19dbe4be919d80dbbbf5e5 a494cad109ae890732063c2631da2c7aca015862a656f1e11ec6bc7d808d1f77
```

实际命令：`uv run --python 3.11 --group dev python -m pytest tests/unit/generation -q -p no:cacheprovider` 410 passed（禁用插件导致既有 cache_dir 配置 warning）；`ruff check src tests` PASS，`ruff format --check src tests` 63 files，`mypy --explicit-package-bases src/scheduler_core/generation src/scheduler_core/generate.py tests/unit/generation` 18 files PASS，均用相同 uv 前缀。`PYTEST_ADDOPTS=-p no:cacheprovider` 且缓存置系统临时目录下运行 `uv run --python 3.11 --group dev python tools/check.py`：718 passed、1 skipped（本机 Windows symlink unavailable），layout/import/source、ruff、format、mypy 67 files PASS。`git diff --check` 退出0，仅既有 CRLF 提示。独立探针使用系统临时文件；未改受审源码、测试或配置。

局限：root 确认未保存可选修前源码快照，故不能逐行独立核验修前后差异或证明旧断言逐字未变；结合此前审查、当前实现、独立探针、9 次哈希及 root 报告的修前后135样本合并摘要一致判断。相同 RNG 状态验证可重复消费，不能单独证明相对修前抽取序列；跨版本哈希证据补充此限制。此前 Windows 文件系统探针及未动态验证 Linux 等限制仍适用。本结论仅 G3，回归锁、G5、提交与同步由 root 执行。
