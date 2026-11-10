# P1-B-R1 独立 G3 审查

结论：REWORK。模型与派发配置：gpt-6.1-terra、high、fork none（按派发记录）；基线 799ea56。

## 发现

- [P2] `src/scheduler_core/validation/resources.py:100`、`:147`、`:205`：容量事件累计扫、日历窗口合并与二分、RUNNING 窗口事件扫仍在资源规则中；`intervals.py` 仅包含最大 end 持有者扫描。Claude 工作包目标明确将纯区间算法置于 intervals，并要求设备规则调用 intervals、不自行写扫描；实施顺序 B.1 亦要求先抽纯算法。G1 的六模块收敛仍保留 intervals 作为无领域对象的区间算法职责。建议将上述纯计算抽入 intervals，资源层只负责领域转换与报告，保持原事件排序、去重与完整报告行为，并重新完成差分和检查。此为职责与可读性未完成，不是已观察到的行为差异。

## 已核验

- `python tools/verify_source.py` 全部通过。
- 基线及现有测试 AST 对照：34 个 test 函数名和参数装饰器全部相同；115 个 assert 中 114 个完全相同，唯一变化为授权的跨文件 inventory 名称检查。其余两个变化测试体仅改 fixture/源码根路径；所有旧 helper AST 相同，无通配导入。REASON_COVERAGE 的 61 令牌与 2049/3780 穷举断言保留。收集 ID 的基线逐项运行对照本审查未独立执行，根设计师阶段 A 已核验。
- 独立内存 pytest 插件对新旧 validate 每次调用分别执行并比较完整 model_dump_json 或异常类型及消息：6044 次一致，其中 2 次异常；覆盖所有测试和 5829 oracle；162 passed、1 原符号链接 skip。独立增加 35 个实例，包括容量 4 RUNNING 绑定/未绑定/失配、DONE、free 不同取值、坏引用、环、自环、重复 task 冻结状态冲突及重复记录冲突，报告和异常一致。mini 与篡改经完整测试套件覆盖。签名及 docstring 与旧版相同。内存加载旧实现，无旧实现落盘。
- `uv run --python 3.11 --group dev python tools/check.py`：layout/import/source、162 passed/1 skip、ruff、format、mypy 均通过。另独立 pytest 使用 `-p no:cacheprovider`，162 passed/1 skip，因禁用插件有 cache_dir 配置警告。
- AST 扫描所有新源码模块无 numpy/random/ortools、反向导入及内部环。文件行数 validate 67、execution 190、index 78、intervals 14、report 44、resources 238、task_rules 135、init 1；最长函数 check_running_blocks 72、check_end_changes 62，均低于 80，但前者内含扫线，见发现。入口 validate 46 行。未发现继承、插件、动态注册或旧实现副本。
- 写入范围对照：代码变更限于批准的 validate、validation 和迁移测试；其他治理文档为总设计师授权范围。未修改模型、轴、上下文、工具、依赖、锁及来源。

最终 ACCEPT 待上述职责问题返工并复审；本次差分覆盖不构成所有可能输入的形式证明。

## 返工复审与关闭

最终 G3：ACCEPT。此前 P2 关闭：容量累计、窗口合并与查找、跨组扫描已移至只依赖标准库及基本值的 `intervals.py` 五个函数；`resources.py` 保留领域判断及报告，人员和设备窗口复用纯函数。核对事件排序、参与者和输出处理与先前实现对应；105 行 intervals 中最长函数 31 行，179 行 resources 中最长函数 49 行。

在最终源码上独立重跑内存双调用差分：6044 次一致（6042 报告 JSON，2 异常类型与消息），覆盖完整测试及 5829 oracle；162 passed、1 原 skip，禁用 cacheprovider 导致一条 cache_dir 配置警告。此前 35 个自造边界在最终树再次执行，全部一致。最终 `uv run --python 3.11 --group dev python tools/check.py`：162 passed、1 原 skip，layout、imports、source、ruff、format 和 mypy 全 PASS。旧实现仅在内存中加载。签名、docstring 与迁移测试的此前核验仍适用；收集 ID 基线逐项对比由总设计师执行，本审查静态核对函数与参数装饰器并独立重跑全部测试。差分结果不构成所有输入的形式证明。
