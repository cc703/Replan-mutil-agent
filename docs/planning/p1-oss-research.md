# P1 开源调研（评审草稿）

检索日期：2026-11-09，Asia/Shanghai。所有候选仅供参考，不引入依赖、不复制源码、不变更既定 CP-SAT 主线。版本与平台支持依据包元数据，并非安装或运行验证。原设计对人员、时间及 V2/V7/V9 的问题见 [P1 开工准备](p1-readiness.md)；具体契约仍待用户裁决。

## 项目 1：OR-Tools v9.15

[固定版本仓库](https://github.com/google/or-tools/tree/v9.15)；[官方文档](https://developers.google.com/optimization/scheduling)。固定路径：[job-shop](https://github.com/google/or-tools/blob/v9.15/ortools/sat/samples/minimal_jobshop_sat.py)、[flexible job-shop](https://github.com/google/or-tools/blob/v9.15/examples/python/flexible_job_shop_sat.py)、[人员班次](https://github.com/google/or-tools/blob/v9.15/examples/python/shift_scheduling_sat.py)；这些路径已通过官方目录或原始文件核对存在。[LICENSE](https://github.com/google/or-tools/blob/v9.15/LICENSE) 为 Apache 2.0；固定仓库递归树未发现 NOTICE 文件名，发行包未核验，范围见下表。复制或再分发前须复核完整许可、相关 NOTICE、版权与修改标记。分类：仅参考。

Python/Windows：对应 [9.15.6755 PyPI 元数据](https://pypi.org/pypi/ortools/9.15.6755/json) requires-python >=3.9，提供 cp311-cp311-win_amd64 wheel；仅为分发元数据证据。建模：作业次序、区间互斥、可选替代方案与人员班次布尔变量值得参考；校验：示例约束属于求解模型，不能充当本项目独立校验器；日历：可参考区间阻塞思想，但三个示例不能证明完整人员日历语义；测试：构造小实例核对约束和结果，示例本身不构成本项目性质测试。局限：示例并不定义本项目 V7、V2/V9 或取整，亦无独立校验保证。

## 项目 2：PyJobShop v0.0.9

[固定仓库](https://github.com/PyJobShop/PyJobShop/tree/v0.0.9)、[官方文档](https://pyjobshop.org/stable/)；[README](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/README.md)、[模型](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/pyjobshop/Model.py)、[测试](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/tests/test_Model.py)、[配置](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/pyproject.toml)路径已核对。[LICENSE.md](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/LICENSE.md) 为 MIT；固定仓库递归树未发现 NOTICE 文件名，发行包未核验，范围见下表。代码复制前须核对完整许可和版权保留义务。分类：仅参考，不建议引入或替换 CP-SAT。

该版本声明 Python >=3.10，[PyPI 固定版本元数据](https://pypi.org/pypi/pyjobshop/0.0.9/json)有 py3-none-any wheel；它依赖 OR-Tools，后者提供 Windows cp311 wheel，传递依赖完整兼容性尚未验证。README 声明支持 CP Optimizer，列出 breaks、可选任务、先后及多模式；模型与数据类未定义独立 Skill 对象，详见下方源码证据。建模可参考任务、资源与模式分离；校验可观察模型输入检查，不能代替独立计划验证；日历可参考资源 breaks，但本项目的阻塞窗口边界须决定；测试按 Model、ProblemData、Solution 等分文件，值得参考边界样例组织。局限：替代后端和库自身语义不构成项目决策；不同系统的语义不能自动等价。

## 依赖核验（截至检索日）

发布日期为 PyPI 对应 wheel 上传的 UTC 日期；包元数据的许可证表达式并非完整分发合规审查。候选为评审候选，不是引入或锁定决策。所有版本均未安装、未做实际联测。

| 包及官方元数据 | 最新稳定 / 发布 / requires-python | Python 3.11 Windows 候选 / 文件 / 发布 | 许可证与判断 |
|---|---|---|---|
| [pydantic](https://pypi.org/pypi/pydantic/2.14.3/json) | 2.14.3 / 2026-11-05 / >=3.10 | 2.14.3 py3-none-any；其强制 [pydantic-core 2.50.4](https://pypi.org/pypi/pydantic-core/2.50.4/json) 有 cp311 win_amd64 wheel | MIT；最新满足元数据条件，传递依赖联测未核实 |
| [numpy 最新](https://pypi.org/pypi/numpy/2.5.4/json)、[候选](https://pypi.org/pypi/numpy/2.4.6/json) | 2.5.4 / 2026-10-10 / >=3.12 | 2.4.6 cp311-cp311-win_amd64 / 2026-05-18；>=3.11 | 最新表达式 BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0；候选同为上述表达式；完整分发许可待核验。最新不支持 3.11 |
| [pytest 最新](https://pypi.org/pypi/pytest/9.2.0/json)、[现有](https://pypi.org/pypi/pytest/8.3.5/json) | 9.2.0 / 2026-10-27 / >=3.10 | 保留 8.3.5 py3-none-any / 2025-03-02 / >=3.8 | MIT；最新虽满足 Python 元数据，但升级无本包授权且插件兼容未验证 |
| [hypothesis](https://pypi.org/pypi/hypothesis/6.170.15/json) | 6.170.15 / 2026-11-06 / >=3.11 | 6.170.15 cp311-cp311-win_amd64 / 2026-11-06 | MPL-2.0；最新版可作候选，许可证义务与集成须先审查 |
| [ortools](https://pypi.org/pypi/ortools/9.15.6755/json) | 9.15.6755 / 2026-01-14 / >=3.9 | 同版 cp311-cp311-win_amd64 / 2026-01-14 | Apache 2.0；与示例 v9.15 对齐，传递依赖须独立核对 |

pytest 8.3.5 与自身相容；Hypothesis 的 pytest extra 元数据要求 pytest>=4.6，8.3.5 满足版本约束。其余包不声明针对 pytest 8.3.5 的兼容保证；未安装联测，不能将元数据视为运行兼容性。

## 六项议题映射

| 议题 | 可参考 | 不适用/未决 |
|---|---|---|
| 人员资源 | 1 班次变量、2 资源模式 | 不证明人员技能契约；缺字段不得判通过 |
| 人员日历 | 2 breaks | 半开边界、重叠与阻塞窗口规则须裁决 |
| V7 | 1 人员分配约束 | 独立校验须独立实现，不能复用求解模型 |
| 设备容量 V2/V9 | 1 资源互斥 | 单容量示例不能决定多容量累计或阻塞消耗 |
| 时间取整 | 1 整数时间模型 | 未证明输入舍入规则；须用户决定 |
| 测试 | 2 按模型分层；Hypothesis 可候选性质测试 | 不以示例通过等同业务验收；缺失、边界、篡改均须覆盖 |

## 未核实与裁决

发行包内额外许可和全部传递依赖尚未核验；Python 3.11 Windows 安装和运行联测 NOT-RUN，本包禁止安装，不作为本调研的验收前提。未引入、复制或安装任何条目。人员字段与 V7、V2/V9 容量、时间取整均须用户审查具体提案；B1 位置与双 profile 维持 DEFERRED-BY-USER。新增依赖及复制代码先取得授权并核对许可。本稿完成元数据范围内的调研，待独立 G3 审查，不声称已验收。

### 补充源码核对

2026-11-09 直接读取固定版 [solve.py](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/pyjobshop/solve.py)、[ProblemData.py](https://github.com/PyJobShop/PyJobShop/blob/v0.0.9/pyjobshop/ProblemData.py) 与前述 Model.py：默认后端 `ortools`，可选 `cpoptimizer`；Model 提供 machine、renewable、consumable、task 和 mode。上述文件中未找到独立 skill 对象，但这不排除其他路径或用资源/模式编码技能。ProblemData 检查 break 起点非负、起点小于终点、窗口互不重叠，并允许边界相接；其 `allow_breaks` 支持任务跨休息中断，setup 也可发生在 machine break 内。这些具体语义仅作对照，不直接移植为本项目规则。

两个项目的根许可文本已读取：MIT 要求随副本保留版权及许可声明；Apache 2.0 对再分发包括提供许可、标记修改、保留相关声明和适用 NOTICE 的义务。根 NOTICE 均 404；递归树结果见下表，不对未下载发行包作断言。实际复制仍须用户决定并完成专项许可核验。

### 固定提交、许可证范围及兼容性补充

通过 GitHub 官方 `commits/{tag}` 与 `git/trees/{full_sha}?recursive=1` 核对：

| 项目 | 标签解析的完整提交 | 递归树范围 | LICENSE / NOTICE 文件名检查 |
|---|---|---|---|
| OR-Tools | [551ad10d94835c99e5e1e684500d3db398c0e345](https://github.com/google/or-tools/tree/551ad10d94835c99e5e1e684500d3db398c0e345) | 5121 项，truncated=false | `LICENSE`，另有 `ortools/julia/ORTools.jl/LICENSE`、`ortools/julia/ORToolsBinaries.jl/LICENSE.md`、`ortools/julia/ORToolsGenerated.jl/LICENSE.md`；以文件名含 license、notice、copying 不区分大小写检索，无 NOTICE 文件名 |
| PyJobShop | [5e1cbee697f44ca451fcdd8c6fb97bec151930d5](https://github.com/PyJobShop/PyJobShop/tree/5e1cbee697f44ca451fcdd8c6fb97bec151930d5) | 137 项，truncated=false | `LICENSE.md`；同一文件名条件无 NOTICE 文件名 |

该检查仅覆盖仓库树路径，不覆盖文件内容中的引用及未下载发行包。固定源码许可链接：[NumPy 2.4.6](https://github.com/numpy/numpy/blob/v2.4.6/LICENSE.txt)、[Pydantic 2.14.3](https://github.com/pydantic/pydantic/blob/v2.14.3/LICENSE)、[pytest 8.3.5](https://github.com/pytest-dev/pytest/blob/8.3.5/LICENSE)、[Hypothesis 6.170.15](https://github.com/HypothesisWorks/hypothesis/blob/v6.170.15/LICENSE.txt)、[OR-Tools v9.15](https://github.com/google/or-tools/blob/v9.15/LICENSE)。NumPy 根源码许可 BSD-3-Clause；候选 PyPI 分发表达式还列 0BSD、MIT、Zlib、CC0-1.0，不能把根源码许可当成 wheel 全部许可。未来实际引入时核验发行文件与传递依赖。Hypothesis 固定版本 PyPI 标识 MPL-2.0，已读取该固定标签根许可证声明；未下载发行文件。

[ProblemData 固定源码](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/ProblemData.py#L89)定义 Machine、Renewable、Consumable、Task、Mode；[Model.add_mode](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/pyjobshop/Model.py#L216) 将任务关联所需资源及 demand；所检查模型、数据类没有独立 Skill 类型或 skill 字段。正例：把有资质人员分别建成资源，任务仅创建合格人员对应 mode，可表达部分技能可行性；反例：没有技能字段时，不能自动校验人员技能变更，也无法单靠模式结构证明本项目 Person/required_skill 和 V7，仍需独立人员语义与验证。具体模型是否足够须用户裁决。[测试示例](https://github.com/PyJobShop/PyJobShop/blob/5e1cbee697f44ca451fcdd8c6fb97bec151930d5/tests/test_ProblemData.py#L281) 检查 mode 属性并参数化非法输入；可参考正反例结构。

候选 Python 要求：pydantic 2.14.3 >=3.10（强制 core 2.50.4 亦 >=3.10 且 cp311 Windows wheel）、numpy 2.4.6 >=3.11、pytest 8.3.5 >=3.8、hypothesis 6.170.15 >=3.11、ortools 9.15.6755 >=3.9。对应 wheel 与日期见上表；前四个包除 Hypothesis pytest extra >=4.6 外未声明针对 pytest 8.3.5 的运行兼容保证；OR-Tools 也未声明。pytest 8.3.5 自身为现有版本。此结论仅为元数据约束判断，动态安装和联测 NOT-RUN。

### Hypothesis 专项许可证门禁（G4 PENDING）

Hypothesis 6.170.15 的 MPL-2.0 属于 [开源工具规范](../engineering/open-source-policy.md) 指定须向用户提出裁决的许可类别。未来实际引入前，必须提交用户 G4 裁决；提案需具体说明链接方式、修改范围、分发方式和替代方案。当前仅做参考调研，未安装、未引入，不在此时提前要求用户批准，也不将一般依赖审查视作该 G4 已完成。

可供未来提案比较的选项：A 保留原规格中的 Hypothesis 要求，提交 MPL 专项裁决后按决定实施；B 先采用已选 NumPy Generator 编写有界生成测试及标准库参数化测试，评估覆盖和维护成本，再由用户决定如何处理原规格的 Hypothesis 要求。B 只是候选，不实施、不自行移除原规格要求，也不改变评估协议。最晚裁决点为实际引入 Hypothesis 之前；拒绝或暂缓只阻塞依赖该引入的工作。
