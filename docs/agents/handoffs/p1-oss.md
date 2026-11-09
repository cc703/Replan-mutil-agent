# OSS-1 交接

状态：DONE（G2 调研交付，可交独立 G3；不声称 G3 ACCEPT）。

模型与运行：总设计师派发配置 GPT-6.1 Terra、high、fork none；本会话无法独立查询运行时实际模型，实际模型未能独立确认。起点 `git status --short` 显示 CHANGELOG、registry、PROGRESS 已修改，多个提示词与 Claude 计划未跟踪，系共享工作树并行归档；未回退或认作本包修改。

变更文件：
- 新增 `docs/planning/p1-oss-research.md`：固定版本来源、依赖元数据、六议题映射、未核实事项与裁决边界。
- 新增 `docs/agents/handoffs/p1-oss.md`：本交接。

项目分类：OR-Tools v9.15、PyJobShop v0.0.9 均仅参考；拟复制代码 0；新增依赖 0。

验证（实际命令与输出）：
- `python tools/verify_source.py`，退出 0；三份原文 bytes、lines、sha256、encoding、LF 与各批次均 PASS。
- 设置 `PYTHONDONTWRITEBYTECODE=1`、`RUFF_CACHE_DIR=artifacts/tmp/ruff-cache`、`MYPY_CACHE_DIR=artifacts/tmp/mypy-cache` 后运行 `uv run --python 3.11 --group dev python tools/check.py`，退出 0：`Layout: PASS`、`Imports: PASS`、原文核验 PASS、`33 passed, 1 skipped in 8.09s`（`symlinks unavailable`）、`All checks passed!`、`6 files already formatted`、`Success: no issues found in 4 source files`。此检查入口内部 pytest 未带 `-p no:cacheprovider`，与派发要求有偏差；未修改检查器。
- `uv run --python 3.11 --group dev python -m pytest -q -p no:cacheprovider tests/governance`，退出 0：`33 passed, 1 skipped, 1 warning in 7.95s`；跳过原因 `symlinks unavailable`；警告 `Unknown config option: cache_dir`，由禁用插件产生。
- 官方 HTTP 仅读取 PyPI JSON、GitHub 内容 API 与 raw 文件；未安装、下载发行包或执行第三方源码。原文哈希核验早于调研。测试仅为治理检查，不代表 P1 业务验收。

来源：见调研稿中的各固定版本官方链接；检索日 2026-11-09。未核实：发行包内额外许可、全部传递依赖；安装与运行联测 NOT-RUN，禁止安装且不属本包前提。固定源码的技能表示、后端及仓库 LICENSE/NOTICE 文件名范围已核实，参见调研稿。

与合同的偏差：`tools/check.py` 间接运行的 pytest 未显式禁用 cacheprovider，已另行以指定参数复测。G3 由独立审查决定。

未决问题：发行包及传递依赖在未来引入前核验；本次候选未安装、未联测。

需裁决问题：人员资源契约与 V7、设备容量 V2/V9、时间取整等须待完整提案后由用户裁决；在具体提案准备前不请求用户提前批准。B1 与双 profile 按用户决定 DEFERRED-BY-USER。

下一步建议：交独立 G3 审查，接受后再进入 P1-0。

补充验证：2026-11-09 再执行同一 `tools/check.py` 命令，退出 0；`33 passed, 1 skipped in 8.07s`，布局、导入、原文、ruff 和 mypy 均通过；内部 pytest 未禁用 cacheprovider 的偏差如上，已有指定参数独立复测。官方 GitHub 两仓库 full commit 递归树返回 `truncated=false`，LICENSE/NOTICE 文件名范围见调研；已直接读取 Hypothesis `v6.170.15/LICENSE.txt`，此前错误猜测标签返回 404 后已核正。

### G3 R1 修复记录（2026-11-09）

独立审查 R1 要求明确 Hypothesis 的 MPL-2.0 专项门禁。已在调研稿补充：依据 `docs/engineering/open-source-policy.md`，未来实际引入前须提交用户 G4，状态 PENDING；具体提案应说明链接方式、修改范围、分发方式及替代方案。补充仅使用已选 NumPy Generator 的有界生成和标准库参数化测试作为待比较选项；不移除原规格 Hypothesis 要求、不改变评估协议、未安装或引入依赖。当前仅供 G3 复审，不要求用户提前批准。

本次修复只改调研稿和本交接；依据独立审查交接及开源工具规范，未执行新测试（纯文档补充）。
