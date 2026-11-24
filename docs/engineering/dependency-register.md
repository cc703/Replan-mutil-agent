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

## P2-1 OR-Tools 开发环境

2026-11-11：用户授权本机开发、测试和运行，二进制对外打包分发前另审，不提交 wheel。`ortools==9.15.6755` 已锁定和安装；[PyPI 固定版本及 wheel](https://pypi.org/project/ortools/9.15.6755/)，[对应源码 Apache-2.0](https://github.com/google/or-tools/blob/v9.15/LICENSE)，[依赖构建配置](https://github.com/google/or-tools/blob/v9.15/cmake/dependencies/CMakeLists.txt)。CP-SAT 为既定方案，标准库不提供该求解器；不新增服务。发布文件与官方源码为维护证据，未作漏洞审计。Apache 分发须提供许可、保留适用版权及 NOTICE、修改文件须注明变更，专利条款亦须审查。

Windows cp311 wheel SHA256 `781fb09d6c9f46015291f706bd7c7e0815db1bec6e92c74716342fb7ea2d0532`，实际包含 abseil、bz2、highs、protobuf、scip、utf8 validity、re2、zlib 等 DLL；wheel 仅发现顶层 LICENSE，未完整核实静态链接与全部捆绑组件版本和许可，不能把根许可覆盖所有组件。源码构建配置的候选版本不能证明该 wheel 的实际构成，bzip2 引用 master。发行前须完成实际 wheel 全组件、许可及 NOTICE 审查。用户此次批准仅覆盖本地使用。

锁定传递依赖的已安装元数据：absl-py 2.5.1 Apache-2.0；immutabledict 4.3.1 MIT；pandas 3.1.1 BSD-3-Clause（wheel 另列多项第三方许可）；protobuf 6.33.6 BSD-3-Clause；python-dateutil 4.0.0 BSD-3-Clause；tzdata 2026.6 Apache-2.0；已有 typing-extensions 4.16.0 PSF-2.0、numpy 2.4.6。版本来源 `uv.lock`，官方固定版本元数据可通过 `https://pypi.org/pypi/<包名>/<版本>/json` 核查；此为包元数据而非完整分发审计。MIT/BSD 再分发需保留版权、许可及免责声明，PSF 与 Apache 按各文本履行；实际 wheel 的附带许可、NOTICE 与二进制义务仍须发行前逐项核查。锁定保留既有版本；安全扫描未执行。

## P6 LangGraph

2026-11-17 引入直接依赖 [langgraph 1.0.10](https://pypi.org/project/langgraph/1.0.10/)（MIT，版本固定于 `pyproject.toml` 和 `uv.lock`），用于可恢复的人工确认图；标准库不提供既定 LangGraph 图/中断能力。[官方中断文档](https://docs.langchain.com/oss/python/langgraph/interrupts) 与已安装版本的 `StateGraph.compile`、`interrupt`、`Command` 和 `InMemorySaver` 签名已核对。固定发行包提供维护证据；未做漏洞或完整发行审计。

2026-11-17 用户批准仅本机开发、测试和运行，未来对外打包分发前另审；不修改第三方代码，不将 wheel 或二进制入库。链路包括 langgraph → langgraph-sdk → orjson、httpx → certifi。已安装元数据标识 orjson 3.13.0 为 `MPL-2.0 AND (Apache-2.0 OR MIT)`，certifi 2026.10.23 为 MPL-2.0。MPL 与其他许可的实际分发义务须依交付形式、完整许可及附带 NOTICE 另审，不能以本地使用批准替代发行审查。

其余本次新增包的已安装版本与许可字段：langgraph-checkpoint 4.3.2、langgraph-prebuilt 1.0.13、langgraph-sdk 0.3.15、langchain-core 1.8.1、langchain-protocol 0.0.21、langsmith 0.14.17、anyio 4.16.0、charset-normalizer 3.5.2、h11 0.16.0、truststore 0.10.5、urllib3 2.8.0 为 MIT；httpx2 2.16.2、httpcore2 2.16.2、uuid-utils 0.19.0、zstandard 0.25.0、jsonpatch 1.47、jsonpointer 3.12、httpcore 1.0.9、httpx 0.28.1、idna 3.20、websockets 17.4 为 BSD-3-Clause；xxhash 4.1.0 为 BSD-2-Clause；requests 2.34.2、requests-toolbelt 1.0.0、distro 1.9.0、tenacity 9.2.1 为 Apache-2.0；ormsgpack 1.13.1 为 Apache-2.0 OR MIT；sniffio 1.3.1 为 MIT OR Apache-2.0。可通过 `https://pypi.org/pypi/<名称>/<版本>/json` 查询官方固定版本元数据，实际发行前仍须逐包核验完整许可、捆绑内容和通知。

2026-11-17 对照 DeepSeek 官方 [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)、[模型列表](https://api-docs.deepseek.com/api/list-models/) 和 [思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)：接口分别为 POST `/chat/completions`、GET `/models`；非思考使用 `thinking.type=disabled`。配置 ID 为 `deepseek-flash`，仅作为配置读取；在线启动须实际列模型精确匹配，无法连接或缺失时停止，不调用付费模型作本次验证。离线传输替身和真实 API 不等价，线上服务能力与计费未在本次调用验证。

## P7 本地应用

2026-11-24 从官方固定版本元数据、已装包与锁文件核实。Python Web 边界完全位于 `src/service/`，正式排程仍走原内核。

| 依赖 | 版本与许可证 | 用途/已核接口 |
| --- | --- | --- |
| [FastAPI](https://pypi.org/project/fastapi/0.115.12/) | 0.115.12，MIT | Pydantic 请求、内部 REST、`app.openapi()` 合同导出。 |
| [Uvicorn](https://pypi.org/project/uvicorn/0.34.3/) | 0.34.3，BSD-3-Clause | `uvicorn.run`，实际 Python 3.11 回环服务和追踪回显已预检。 |
| [HTTPX](https://pypi.org/project/httpx/0.28.1/) | 0.28.1，BSD-3-Clause | 已有 P6 传递依赖提升为直接依赖；HTTP E2E 使用同步 Client。 |
| [Starlette](https://pypi.org/project/starlette/0.46.2/)、[Click](https://pypi.org/project/click/8.5.1/) | 0.46.2 和 8.5.1，BSD-3-Clause | FastAPI/Uvicorn 新增传递依赖。既有锁定版本未更新。 |
| [PostgreSQL](https://www.postgresql.org/about/licence/) | 17.12，PostgreSQL License | 真实本地数据库。使用 [Windows 二进制](https://www.postgresql.org/download/windows/) 实测 UTF-8、SCRAM 回环连接；[SQL 行锁与 SKIP LOCKED](https://www.postgresql.org/docs/17/sql-select.html)。容器方案固定镜像标签，不入库镜像。 |
| [Apache Maven](https://release-catalog.apache.org/maven/3.9.11/index.html) | 3.9.11，Apache-2.0 | Windows JDK 17 下运行，构建工具与缓存不入库。 |

前端锁文件内的 BlueOak-1.0.0 条目为传递依赖。[许可证全文](https://blueoakcouncil.org/license/1.0.0)给出宽松许可，复制时随附许可证或链接，[OSI 已批准](https://opensource.org/license/blueoak-1.0.0)。未打包分发第三方依赖、运行镜像或二进制。

| 依赖 | 版本与许可证 | 用途/核实来源 |
| --- | --- | --- |
| [Spring Boot](https://repo.maven.apache.org/maven2/org/springframework/boot/spring-boot-starter-parent/3.5.8/) / Spring Framework | 3.5.8 / 6.2.14，Apache-2.0 | 官方 Maven POM/BOM；REST 控制器、HTTP 网关、事务控制与工作线程。 |
| [MyBatis-Plus Boot 3 starter](https://repo.maven.apache.org/maven2/com/baomidou/mybatis-plus-spring-boot3-starter/3.5.14/) / MyBatis / MyBatis-Spring | 3.5.14 / 3.5.19 / 3.0.5，Apache-2.0 | 原设计数据层选项，沿 MyBatis Mapper 执行参数绑定的 PostgreSQL SQL。 |
| [Flyway](https://repo.maven.apache.org/maven2/org/flywaydb/flyway-core/11.7.2/) 与 [PostgreSQL 模块](https://repo.maven.apache.org/maven2/org/flywaydb/flyway-database-postgresql/11.7.2/) | 11.7.2，Apache-2.0 | 版本化迁移及数据库部分唯一索引。 |
| [PostgreSQL JDBC](https://repo.maven.apache.org/maven2/org/postgresql/postgresql/42.7.8/) | 42.7.8，BSD-2-Clause | JSONB、事务、UTC 会话和真实本地 PostgreSQL 连接。 |
| [嵌入式 Tomcat](https://repo.maven.apache.org/maven2/org/apache/tomcat/embed/tomcat-embed-core/10.1.49/) / [Tomcat Annotations API](https://repo.maven.apache.org/maven2/org/apache/tomcat/tomcat-annotations-api/10.1.49/) / [Log4j2](https://repo.maven.apache.org/maven2/org/apache/logging/log4j/log4j-core/2.24.3/) | 10.1.49 / 10.1.49 / 2.24.3，Apache-2.0 | 嵌入式 HTTP 容器、其兼容 Java 注解、JSON 结构化日志。排除默认 Logback、单独的 Jakarta 注解实现。 |
| [Vue](https://registry.npmjs.org/vue/3.5.30)、[Vue Router](https://registry.npmjs.org/vue-router/4.6.4)、[Element Plus](https://registry.npmjs.org/element-plus/2.13.5) | 3.5.30、4.6.4、2.13.5，MIT | 响应式界面、页面路由、表单和确认交互。 |
| [vis-timeline](https://registry.npmjs.org/vis-timeline/8.5.0) 与 [Moment](https://registry.npmjs.org/moment/2.30.1) | 8.5.0，Apache-2.0 OR MIT；2.30.1，MIT | D3；[官方 Timeline API](https://visjs.github.io/vis-timeline/docs/timeline/) 的设备组、任务范围、背景窗口和时间显示。npm 锁定对等依赖。 |
| [TypeScript](https://registry.npmjs.org/typescript/5.9.3)、[Vite](https://registry.npmjs.org/vite/7.3.1)、[Vitest](https://registry.npmjs.org/vitest/4.0.18)、[Playwright](https://registry.npmjs.org/@playwright/test/1.61.1) | 5.9.3 Apache-2.0；7.3.1、4.0.18 MIT；1.61.1 Apache-2.0 | Node 24 下类型检查、回环构建预览、组件证据与 Chromium 浏览器验收。测试辅助包与传递版本见 npm 锁和各交接。 |
