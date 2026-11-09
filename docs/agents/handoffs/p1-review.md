# P1 独立审查交接（分阶段）

日期：2026-11-09（Asia/Shanghai）；角色 reviewer v001；实际派发配置 gpt-6.1-terra / high / fork_turns=none。工作包 OSS-1、P1-0；审查提示词 p1-review.v001。本人未参与被审包实施。

## 阶段 0：档案前置 — PASS

四份提示词的 BEGIN/END 标记内正文按 UTF-8 计算 SHA256，均等于其声明值，且与所声明的渲染捕获行逐字相等：

| 提示词 | 捕获行 | payload SHA256 |
|---|---|---|
| p1-contract.v001 | v001:16–64 | 0cf0a2a515c9ada943f6ecdf1b489b4e89ce7b3aec2c945c14aa33c3a97bc302 |
| p1-oss.v001 | v002:42–91 | 3cb33168792343ef951c5555ea7a14e921b37f7608b0e5e43bfd2987ef368b8c |
| p1-contract.v002 | v002:95–164 | f416d1c94ca4121bb12c61735ae3cabb33d53911a891a4914e6eb4ce22d38d8f |
| p1-review.v001 | v002:168–216 | 67a3da623333b5b87194f572e8d29d1cd6f9300eb8e1742108f2921d3162a36b |

捕获全文 SHA256 分别为 v001 `8cf708c392eab40333dadc0bd84b722f76a64a02af51d7479327586453ea0831`、v002 `5f95467e7f6bfd38b95769b2ac356604562226ffb3bd2b3d9be140e5b21355a9`，与四个摘录头部记录一致。证据仅证明仓库渲染捕获与摘录一致，不证明原始 Markdown 字节或外部会话独立真实性。

Git 状态及 diff 显示七份已跟踪旧提示词无改动；四份新摘录与捕获、派发日志属于总设计师归档。已观察到的其他共享树改动为总设计师登记的进度、索引与日志文件；OSS 正在执行，审查阶段不能据未交付认定失败。上述检查为时点快照，不代替后续交付后的范围复核。

G1 的分阶段审查将 OSS 工程 G3 ACCEPT 与需要远程同步的整体状态区分，提案依赖前者，未发现循环；未授权代码实现、依赖安装或批准契约。实际派发日志记录 OSS 与本审查使用 Terra/high/fork none，文件范围与 G1 表一致；提案尚未派发。日志中本 reviewer 消息与本次收到的任务一致；实际模型配置依据派发记录，无法从审查文档独立核实运行时底层模型。

发现：本阶段无阻断发现。G1 的等价类、默认字段与缓存解释须在后续交付审查中按原文覆盖和实际生成文件再次检验，前置 PASS 不代表被审交付 ACCEPT。

## 后续状态

- OSS-1：IN-PROGRESS，交付和工程 G3 **待审**；许可证表与外部来源尚未核对。
- P1-0：**NOT-STARTED**，待 OSS 工程 G3 ACCEPT；引用表、V7、兼容性和 G4 未决表尚未审查。
- 用户 G4：PENDING；任何建议均非批准。远端同步暂缓。

## 本次验证和交接

- `python tools/verify_source.py`：三份原文 bytes、lines、sha256、encoding、LF 及全部 14 批 PASS。
- Python 标准库 hashlib 对四份 payload、两份捕获和行范围比对：均一致；`git status --short`、`git diff --name-only`、`git ls-files docs/agents/prompts` 核对上述范围。
- 未运行完整治理检查、pytest、ruff、mypy 或布局检查；总设计师报告的基线结果不是本人执行结果。
- 本次仅新增本交接文件，用于保留分阶段审查证据；无被审文件修改。未发现需立即提交的新用户裁决；后续 G4 由完整提案审查汇总。
- 下一步：等待总设计师 followup，在 OSS 交付后独立复核；不自行进入提案阶段。

## 阶段 1：OSS 工程 G3 — REWORK

**发现 R1（重要，阻断工程 ACCEPT）**：`docs/planning/p1-oss-research.md:26,44,61` 将 Hypothesis 的 MPL-2.0 写为须审查及新增依赖须授权，但没有明确指出依 `docs/engineering/open-source-policy.md`，未来引入 MPL 候选须先向用户提交 G4 裁决及链接方式、修改范围、分发方式、替代方案；一般授权/审查不应被误读为已完成该特定门禁。建议作者补充明确前置与状态（本轮仅参考，未引入；未来 G4 PENDING），无需现在提前要求用户批准。固定版本 [官方许可证](https://github.com/HypothesisWorks/hypothesis/blob/v6.170.15/LICENSE.txt) 和 [PyPI 元数据](https://pypi.org/pypi/hypothesis/6.170.15/json) 为 MPL-2.0 证据。

### 独立核对表（2026-11-09）

| 条目 | 独立来源与结果 |
|---|---|
| OR-Tools | [v9.15 tag](https://api.github.com/repos/google/or-tools/commits/v9.15) 解析为 `551ad10d94835c99e5e1e684500d3db398c0e345`；三个文档所列固定 Python 示例与根 Apache 2.0 LICENSE 的 raw 文件可读取；[固定递归树](https://api.github.com/repos/google/or-tools/git/trees/551ad10d94835c99e5e1e684500d3db398c0e345?recursive=1) 5121 项、truncated=false，文件名无 NOTICE。 |
| PyJobShop | [v0.0.9 tag](https://api.github.com/repos/PyJobShop/PyJobShop/commits/v0.0.9) 解析为 `5e1cbee697f44ca451fcdd8c6fb97bec151930d5`；根许可为 MIT；[固定递归树](https://api.github.com/repos/PyJobShop/PyJobShop/git/trees/5e1cbee697f44ca451fcdd8c6fb97bec151930d5?recursive=1) 137 项、truncated=false，文件名无 NOTICE。Model.py、ProblemData.py、solve.py 可读取；solve.py 默认 ortools、可选 cpoptimizer；所读模型与数据文件无 skill 字样，有 allow_breaks。具体 breaks 的边界与 setup 细节本轮尚未独立逐条复核，需补查，不凭名称推断。 |
| 依赖与许可 | 直接读取 PyPI 的最新 JSON 和所列固定 JSON：pydantic 2.14.3、numpy 2.5.4、pytest 9.2.0、hypothesis 6.170.15、ortools 9.15.6755 为服务返回最新版；候选 requires-python、所列 Windows cp311/纯 Python wheel 与日期均与表一致。pydantic 强制 core==2.50.4，core 有 cp311 Windows wheel；Hypothesis pytest extra >=4.6。读取五个固定源码许可文件：Pydantic/pytest MIT、NumPy 根 BSD、Hypothesis MPL、OR-Tools Apache；NumPy 分发表达式另含 0BSD/MIT/Zlib/CC0。NumPy 最新 wheel 发布日期待独立补查；pytest/OR-Tools 旧元数据 license_expression 为空，其根许可文本为依据。 |

递归树结果仅覆盖仓库文件名而非文件内容和发行包；本包无复制或安装授权。分发包额外许可、传递依赖、Windows 安装与动态联测均 NOT-RUN，不作为此元数据研究的验收前提。

### 实际检查与范围

本 reviewer 运行：`python tools/check_repo_layout.py` → Layout PASS；`python tools/check_import_boundaries.py` → Imports PASS；`python tools/verify_source.py` → 三原文和 14 批 PASS。`uv run --python 3.11 --group dev python -m pytest -q -p no:cacheprovider tests/governance` → 33 passed、1 skipped（symlinks unavailable）、1 warning（禁用 cacheprovider 后未知 cache_dir），7.98s；`uv run --python 3.11 --group dev ruff check . --no-cache` → All checks passed；`uv run --python 3.11 --group dev ruff format --check . --no-cache` → 6 files already formatted；`uv run --python 3.11 --group dev mypy tools` → 4 source files 无问题。设置 PYTHONDONTWRITEBYTECODE；mypy 缓存指定 artifacts/tmp。检查非业务验收。作者交接如实披露 check.py 内 pytest 未关闭 cacheprovider，后续已单独指定选项重跑；本 reviewer 未运行 check.py。

相对 8a5914d，已跟踪变化为 root 的 dispatch-log、registry、PROGRESS，未跟踪交付为作者两份文件；共享树不能把 root 合法变更当作者越界。无依赖、锁、源码、原文或测试变化。此后本 reviewer 只追加本报告。P1-0 仍 NOT-STARTED，G4 待完整提案；OSS 的 REWORK 修正和上述未完成的细节复核后再作工程 G3，工程 G3 不等同远程同步状态。

### 阶段 1 补核完成

对前表标为待核的项目继续直接读取官方文件：[ProblemData.py:15–22](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L15) 检查非负、起点小于终点、只在前终点大于后起点时拒绝，故允许相接；[同文件:211–213](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L211) 描述 allow_breaks 的中断和恢复；[同文件:534–535](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L534) 声明 setup 可在 machine breaks 内发生。[NumPy 2.5.4 PyPI JSON](https://pypi.org/pypi/numpy/2.5.4/json) 的 wheel 上传 UTC 日期为 2026-10-10，与稿件一致。这两项待核已解除；工程结论仍为 **REWORK（R1 待作者补充）**。

### 阶段 1 R1 定向复审 — 最终工程 G3 ACCEPT

复核 `docs/planning/p1-oss-research.md:67–71` 与 `docs/agents/handoffs/p1-oss.md:31–35`：明确 Hypothesis 的 MPL-2.0 在未来实际引入前须经用户 G4，状态 PENDING，裁决材料须说明链接方式、修改范围、分发方式和替代方案；候选替代仅供比较，明确不擅自移除原规格要求或改变评估协议。R1 已解决，未见新增矛盾。此前 REWORK 保留为真实审查历史。

OSS 工程 G3 **ACCEPT**；可进入 P1-0 文档提案。此结论不授权安装、复制代码或冻结业务契约，也不代表用户 G4 或 Git 远端同步已完成。Windows 动态安装联测及发行包额外许可仍为 NOT-RUN/未核验，未来引入前处理。此次仅执行定向文档阅读与 `git status --short`；不重复前次已完成的网络与治理检查。
