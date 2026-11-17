# P6 实施交接（2026-11-17）

实施依据：`docs/work-packages/p6.md` G1 v001，基线 72930d7。仅实现白名单文件，未提交、推送、修改 Git 配置或运行全仓 check。独立 G3 和 root 集成检查尚未完成。

- `src/agent/ir.py`、`changes.py`：版本化变更 IR、实体/别名及时间检查、核心事件或截止变更转换；软偏好不执行。
- `permits.py`、`store.py`：单次绑定许可、进程内世界/版本和人工决策审计；候选保留对应世界、父计划、free 和验证上下文，在展示/提交/回滚时独立校验。
- `solver.py`、`negotiation.py`、`tools.py`：复用 CP-SAT、影响域、诊断、假设松弛与 diff；超时不作无解，假设松弛不直接授权或提交。
- `graph.py`、`state.py`：实际 LangGraph 图、进程内 checkpoint、澄清及 L1/L2 暂停恢复、查询和回滚。多条变更分次确认；状态、版本及 checkpoint 不跨进程持久化。
- `llm.py`、`defaults.yaml`、`prompts/`：标准库 DeepSeek 接口、模型列表核验、版本化提示与 schema；离线可以注入录制响应。未调用付费模型，真实在线服务及额度未验证。
- `explain.py`、`trace.py`：证据 claim 核对与受控模板，白名单结构化 trace 和 ArtifactStore manifest；决策原文只在进程内，token 不可得时记录 null。
- `evaluation.py`、`miniature.py`、`__main__.py` 和 `data/eval_sets/extraction_smoke/`：离线演示、七类合成管线样例和三次评分；不代表 DeepSeek 准确率，也不构成 D7 正式评测。
- `tests/unit/agent/`：许可、IR、图、真实 CP-SAT、不可行/超时、解释、脱敏、评测与传输替身测试。依赖固定、API 与许可核验见依赖登记；用户批准本机使用，分发另审。

## 首轮实测（历史）

- `python tools/verify_source.py`：全部原文、分批与哈希 PASS。
- `uv run --locked --python 3.11 --group dev python -m pytest -q tests/unit/agent`：21 passed。
- `uv run --locked --python 3.11 --group dev mypy src/agent tests/unit/agent`：24 个文件通过；LangGraph 外部类型重载有一处局部 mypy 标注，运行时图由测试覆盖。
- `uv run --locked --python 3.11 --group dev ruff check src/agent tests/unit/agent` 和 `ruff format --check src/agent tests/unit/agent`：通过。
- PowerShell 设置 `PYTHONPATH=src`、`PYTHONUTF8=1` 后，`'y','y','0' | uv run --locked --python 3.11 python -m agent demo --offline`：退出 0，L1、L2 和选择后提交版本。`uv run --locked --python 3.11 python -m agent eval --offline`：退出 0，七条三次各 7/7，均值 1、方差 0，仅为固定录制响应管线检查。

约束与未验证：无线上 API 实际调用、跨进程恢复、数据库或 Web；运行证据必须由调用方真实提供。相对时间当前支持“今天/明天 HH:MM”，其他形式需澄清；别名由可信调用方提供并拒绝多重匹配。图中的解释使用证据模板；独立审查仍需实测攻击及异常边界，不以作者自测代替 G3。正式 D7 人工样本、标注及防泄漏协议另待具备数据和人员。

## G3 五项返工（待独立复验）

- 图可注入证据专用解释器；在线适配使用 explain v001 提示与 schema，非思考、温度 0，严格验证 claim，错误最多重试两次，耗尽才用模板。图恢复不会重复请求同一证据解释；离线有正确、错误单位及额外自由文本反例。
- 自然语言查询/回滚规则路由及可注入结构化模型路由已接入；`python -m agent chat --offline` 可输入请求并输入录制响应，`chat --online` 从环境取密钥并先校验模型列表。无自然语言确认可替代 L1/L2；未实际访问付费模型。
- 七类 fixture 含独立话语、录制响应和 gold；生产和评测共享变更语义与时间解析入口，多条、相对时间、澄清及类别指标有反例。三次录制样例各 8/8 项，七句各自精确匹配，仅为管线测试。
- 紧急任务 IR 使用带时区的绝对释放/截止时间及 `duration_minutes`，经 TimeAxis 和槽长整除检查转换；回译显示绝对时间和分钟单位。
- 回滚以当前活动计划为父、绑定当前可信快照和版本，计算当前 free 并独立验证；缺失快照拒绝。未来任务回滚成功、伪造/重放及运行中任务不安全回滚拒绝的代表性测试已覆盖。运行中微例需模拟可信执行状态；未声称其完整状态变化已从公开业务事件入口重现。

返工后 `uv run --locked --python 3.11 --group dev python -m pytest -q tests/unit/agent`：30 passed；mypy 24 文件、Ruff check 和 format check 通过。设置 `PYTHONPATH=src`、`PYTHONUTF8=1` 后两条原离线 CLI 均退出 0，额外运行 `chat --offline` 的自然语言查询退出 0。未调用在线付费服务，未运行全仓 check，独立复验未完成。

## G3 再次返工（待独立复验）

- 在线抽取发送可信设备/任务目录、别名、时间轴、业务 now 和单位；解析时按可信目录重新解析唯一引用，不依赖模型填写内部 ID，多匹配与低置信拒绝。
- DeepSeek 每次实际 route/extract/explain 调用记录耗时、状态及可取得的总/输入/输出 token，缺失为 null；各调用记录对应版本提示哈希，不落请求、响应、密钥或异常正文。传输替身测试核验三类哈希、usage 与隐私哨兵。
- 候选事实包覆盖任务前后设备、人员、起止、变更标识、结束/逾期变化、影响分组与理由、计划指标及候选目标；诊断协商将状态、核、最小性证明状态及假设松弛证据交给同一受控 claim 校验与降级路径。证据与路由、变更节点、展示节点按职责从图装配中拆出。
- 评测按单句内匹配再汇总，防止跨句抵消；时间字段独立规范化 UTC，跨时区同一时刻匹配。新增跨句交换负例和等价时区正例。

本轮最终定向 `pytest -q tests/unit/agent`：35 passed；mypy 28 文件、Ruff check/format 全通过。离线 demo 与 eval 均退出 0；eval 三次为 8/8 项的固定响应管线检查，非模型准确率。未调用付费服务、未运行全仓检查；待原独立 G3 复验。

## 路由严格校验补丁（待独立复验）

在已同步 `ab18cc6` 后，路由模型输出统一经严格 Pydantic `RouteSuggestion` 校验，拒绝额外字段、错误目标类型和未知动作；缺失或未知回滚目标进入澄清，实际回滚仍需 L2。改动限于 `routing.py`、`llm.py`、`view_nodes.py` 及对应测试。定向 agent 测试 44 passed；全仓同参数 `mypy --explicit-package-bases tools tests src` 199 文件通过；变动 Python 文件 Ruff 检查与格式检查通过。未运行全仓 check、未调用付费模型、未改 Git 或标签。
