# 依赖登记

本表只登记 P0 治理实际工具与待核实状态；业务技术栈在对应阶段核实后登记。版本的机器来源为 uv.lock，安装状态需以实际命令验证。

| 名称 | 用途 | 固定版本/状态 | 许可证 | 一手来源 | 核实日期 | 维护状态 | 替代 | 工作包 | 审批 |
|---|---|---|---|---|---|---|---|---|---|
| Python | 治理脚本与测试解释器 | 3.11.15，WP-C 实际安装执行 | 待核实具体分发许可 | https://www.python.org/doc/ | 2026-11-09（版本） | 未额外调研 | 无同等替代 | P0-C | 常规工程 |
| uv | 环境与锁文件 | 0.10.10，本机实际运行；CLI 未纳入 uv.lock | 未核实 | https://docs.astral.sh/uv/ | 2026-11-09（版本） | 未额外调研 | pip（需保留可复现锁） | P0-C | 已选方向 |
| pytest | 治理测试 | 8.3.5，已安装并锁定 | MIT（已装发行包 metadata） | https://github.com/pytest-dev/pytest | 2026-11-09 | 本次未额外调研 | unittest | P0-C | 常规工程 |
| ruff | Python 静态与格式检查 | 0.11.13，已安装并锁定 | MIT（已装发行包 metadata） | https://github.com/astral-sh/ruff | 2026-11-09 | 本次未额外调研 | 分离 lint/format 工具 | P0-C | 常规工程 |
| mypy | 类型检查 | 1.15.0，已安装并锁定 | MIT（已装发行包 metadata） | https://github.com/python/mypy | 2026-11-09 | 本次未额外调研 | 暂不引入其他检查器 | P0-C | 常规工程 |

pre-commit、pip-audit、npm audit 为规范中提及的方法，未确认采用和安装时不列为已用工具。
核实方法：实际运行 `uv --version`；在项目环境用 `importlib.metadata.version` 和 `metadata(...).get('License')` 读取 pytest、ruff、mypy 的版本与许可字段。以上链接是官方仓库导航，未声称网页许可证已阅读；修改/再分发工具代码前还须核对相应版本完整许可文本及 NOTICE。metadata 的 MIT 标识不能代替履行其完整义务。
WP-C 已记录治理检查通过，最终验收及同步以项目进度为准。Python 与 uv 完整许可待实际需要分发时核实，不用“未核实”冒充可自由再分发。

## 新条目必填

名称；解决的问题；直接/传递依赖；版本与锁文件位置；官方文档及源码许可链接；检查日期；维护证据；许可义务与 NOTICE；替代方案；引入工作包；审查结论；安装/API/安全验证；需要用户裁决的事项。
