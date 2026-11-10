# P1-B 独立 G3 审查

结论：ACCEPT（工程范围；不代表求解器或上层授权真实性已验证）。模型 GPT-6.1 Terra，high，fork_turns=none。审查依据工作包消息70、Δ-B1、Δ-B2、G1及设计原文，未读取作者会话。

审查中总设计师发现赋值键与 task_id 可变更不一致而误通过；独立确认原实现漏检，作者修复为 V1 ASSIGNMENT_KEY_MISMATCH，plan/base 正反测试与 README 已核。另复核可变实例重复实体 ID，作者补 V1 DUPLICATE_TASK_ID、DUPLICATE_DEVICE_ID、V7 DUPLICATE_PERSON_ID 和正反测试。修复后未发现待处理缺陷。

核对 V1–V11 及 61 reason 与交接表对应的测试函数、实际触发与不触发断言；包含冻结、记录与 base 双绑定、无效或多余证据、授权、邻域、人员、日历、有效及无效 RUNNING 窗口。六类上下文 JSON、ID、槽、默认隔离、extra 与关系受测；执行事件不等于人类确认，确认真实性仍由上层承担。人工 mini 黄金计划通过，篡改触发设备重叠和前驱错误，不宣称求解最优。

独立审查 oracle：2049 重叠实例和 3780 容量实例，itertools 确定性组合；参与任务并集、每分量、条数上界及容量最大溢出段与任务并集由测试中的独立两两/端点算法比较；需求1–3、容量1–4组合均出现，超容量单任务排除扫描。源码扫描为排序与扫描，V6 合并并二分；未见 horizon 逐槽或无输出的全量两两比较。时间界限依输出大小，非性能基准保证。src/tests 无 random/numpy/ortools import 命中；现有模型、axis、依赖及检查入口无本包修改。共享治理文件为总设计师范围。

独立内存探针（有效 1 分钟槽、horizon=10**9）：嵌套同起点报告 V2 [0,1]、[0,2]；端点相接链无违规；capacity=3、demand=1/2/2 报 V9 [0,1,2]、[2,4)，均符合手算。首次探针因未设置 PYTHONPATH 失败，第二次因默认5分钟槽使 horizon 超出 datetime 范围被 TimeAxis 正确拒绝；更正设置后结果如上。测试另核输入深度不变、重排稳定、坏引用与环。

独立命令：`uv run --python 3.11 --group dev python -m pytest tests -q -p no:cacheprovider`：162 passed，1 skipped，1 warning，9.08s；原 skip 是系统不能创建符号链接，warning 是关闭 cacheprovider 后既有 cache_dir 配置。`uv run --python 3.11 --group dev python tools/check.py`：162 passed、1 skipped；layout、import、source、ruff、format、mypy 全通过（15 文件）。独立 `tools/check_repo_layout.py` PASS；`python tools/verify_source.py` 全部原文与分块 PASS。

保守语义按已批准 CB：失败/取消/中断不排，setup 冲突报告并取大值，视野映射 V6，parent 与快照绑定，free=None 省略邻域检查，RUNNING 只在证据与绑定有效时去重；未见扩大业务规则。限制：授权与事件真实性不能由结构验证证明；符号链接运行路径本机未验证；未实现或验证求解、重规划、仿真与最优性。
