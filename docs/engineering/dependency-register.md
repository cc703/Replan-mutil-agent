# 依赖登记

本表登记已引入工具与业务依赖；其他技术栈在对应阶段核实后登记。版本的机器来源为 uv.lock，安装状态需以实际命令验证。

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


## P1-A 数据模型依赖

2026-11-09 核对 `uv.lock`、已安装包 `importlib.metadata`（版本、License-Expression、License-File、Project-URL），及以下固定版本官方元数据。五包均随 `uv sync` 实际安装；Pydantic 核心模型与判别等 API 已通过本包探针及测试。来源的固定版本和发布信息提供维护证据，本次未额外评估未来维护状态或做漏洞审计。

| 包与固定版本 | 关系和用途 | 官方固定版本元数据与源码许可 | 替代及选择 |
|---|---|---|---|
| pydantic 2.14.3 | 直接；类型化数据模型与输入校验 | [PyPI](https://pypi.org/pypi/pydantic/2.14.3/json)，[源码 MIT](https://github.com/pydantic/pydantic/blob/v2.14.3/LICENSE) | 标准库 dataclasses 须自行实现校验；按既定 Pydantic v2 规范选用 |
| pydantic-core 2.50.4 | 传递；Pydantic 校验和序列化核心 | [PyPI](https://pypi.org/pypi/pydantic-core/2.50.4/json)，[对应源码 MIT](https://github.com/pydantic/pydantic/blob/v2.14.3/pydantic-core/LICENSE) | Pydantic 精确依赖，不单独替换 |
| annotated-types 0.8.0 | 传递；类型注解约束元数据 | [PyPI](https://pypi.org/pypi/annotated-types/0.8.0/json)，[源码 MIT](https://github.com/annotated-types/annotated-types/blob/v0.8.0/LICENSE) | 随 Pydantic 解析，不单独替换 |
| typing-inspection 0.4.5 | 传递；运行时类型注解检查 | [PyPI](https://pypi.org/pypi/typing-inspection/0.4.5/json)，[源码许可](https://github.com/pydantic/typing-inspection/blob/v0.4.5/LICENSE)；安装元数据 MIT | 随 Pydantic 解析，不单独替换 |
| typing-extensions 4.16.0 | 传递；跨 Python 版本类型功能 | [PyPI](https://pypi.org/pypi/typing-extensions/4.16.0/json)，[源码许可](https://github.com/python/typing_extensions/blob/4.16.0/LICENSE)；安装元数据 PSF-2.0 | 标准库 typing 不能单独替代依赖指定版本 |

版本和关系以 `uv.lock` 为准；直接依赖在 `pyproject.toml`。MIT 分发时须保留版权和许可声明，PSF-2.0 分发时须保留许可及版权声明，修改时还须按许可说明变更；具体适用义务须以完整许可文本和实际分发形式复核。安装元数据均列有 LICENSE；本次未逐项检查完整发行包、第三方捆绑许可或 NOTICE 内容，不声称已完成发行审计。分发前须检查实际 wheel/源码包及其 NOTICE 和附带许可。P1-A 常规工程引入已按工作包 G1 授权；无新增付费服务或用户业务规则裁决。独立 G3 审查待完成。

P1-C1 ArtifactStore 使用 Python 标准库及已登记 Pydantic；无新增依赖。

## P1-C2 生成器依赖

2026-11-10 核对官方 PyPI 固定版本元数据、Windows CPython 3.11 wheel 及随包许可。版本固定在 `pyproject.toml` / `uv.lock`，均已安装；无新增传递依赖。候选按当前功能需要选择，标准库随机数无法遵循既定 PCG64 子流契约，标准库不含 YAML 解析器。安全漏洞扫描和长期维护状态未核验，发行日期与官方发行文件提供维护证据。

| 包 | 用途及官方来源 | 许可及分发注意事项 |
|---|---|---|
| numpy 2.4.6 | 直接运行依赖，PCG64 和独立子流；[PyPI](https://pypi.org/project/numpy/2.4.6/)、[生成器文档](https://numpy.org/doc/2.4/reference/random/generator.html) | [Windows wheel](https://files.pythonhosted.org/packages/c5/31/7fc6239c12bce7e931463251cca4426c465e1876ba3cc785402ef4dd8f4e/numpy-2.4.6-cp311-cp311-win_amd64.whl) 的 LICENSE 包含 NumPy BSD、OpenBLAS BSD-3-Clause、LAPACK BSD-3-Clause-Open-MPI 及静态 GCC runtime GPL-3.0-or-later WITH GCC-exception-3.1，另含组件许可；见 P1-C2 交接。2026-11-10 用户批准作为开发/运行依赖，未来二进制打包分发前另审，不将 wheel 入库。 |
| PyYAML 6.0.3 | 直接运行依赖，安全读取参数；[PyPI](https://pypi.org/project/PyYAML/6.0.3/) | wheel LICENSE 为 MIT，分发保留版权与许可通知。 |
| types-PyYAML 6.0.12.20261103 | 直接开发依赖，PyYAML 类型桩；[PyPI](https://pypi.org/project/types-PyYAML/6.0.12.20261103/) | wheel LICENSE 为 Apache-2.0；分发时履行许可及适用的 NOTICE 义务。 |

所用固定 wheel 与校验值、运行探针及未测事项见 `docs/agents/handoffs/p1-c2.md`。已用 mypy 1.15.0 对小型 NumPy/PyYAML 类型探针验证；完整项目检查以 G2 实际结果为准。
