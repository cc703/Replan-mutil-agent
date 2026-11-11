# P1-C2 实际实施派发 v001

2026-11-10，实际/root/p1c2_implementation；model=gpt-6.1-terra，reasoning_effort=high，fork_turns=none。主提示词全文另见p1-c2-implementation.v001.md；以下为实际spawn正文。

```text
角色P1-C2专项实施；运行配置gpt-6.1-terra/high/fork_turns=none。绝对工作目录D:/Default/Replan-mutil agent，分支codex/p0-governance，代码基线0d5b394（原250passed/1既有symlink skip、40文件static/source/layout/import通过）。用户已明确授权temp临时替代Claude计划，AGENTS已有例外，不需等Claude额度。temp已完成计划，root于docs/work-packages/p1-c2.md顶部G1 PASS；按工作方式计划→rootG1→你实施自检→独立G3→rootGit。仅当前P1-C2，不跳P2/前后端。
完整实际主提示词是docs/agents/prompts/p1-c2-implementation.v001.md全文，请完整读取照执行；它引用的恢复入口明确为docs/work-packages/p1-c2-claude-initial.md全文→p1-c2-claude-delta.md全文→p1-c2-temp-plan.v001.md全文→p1-c2.md顶部root G1，冲突以后者优先。读取AGENTS/PROGRESS/RESUME、temp角色/工程规范、相关已核验原文及实际models/axis/io/validator/import checker。你有主提示词限定的全部新源码、测试、配置、依赖/lock、README与自身handoffs/p1-c2.md独占写权。root持有AGENTS、进度、registry、RESUME、CHANGELOG、工作包卡片、prompt与Git；不要改它们，不覆盖其他工作。当前未提交文档均root/temp合法规划改动，不是你越界；不切分支/commit/push/改Git配置。
先核实候选numpy2.4.6、PyYAML6.0.3、types-PyYAML6.0.12.20261103官方版本/API/发行许可证/Windows3.11wheel/实际mypy1.15兼容，再按限定引入；不升级旧依赖、不type ignore或缩小mypy。root已只读JSON确认候选版本及wheel存在不是发行许可审计。stub若不兼容可选官方核实较早固定版，不升级mypy。先安装及动态API/发布原语探针，然后再业务代码；途中及时报实际结果。NumPy发行bundle许可必须真实实读，若出现需用户裁决的许可疑问暂停相关而非笼统认BSD无义务。
完整实现原计划+Δ+temp全部功能和有意义验收，不偷省人员/日历/多容量/DAG/可调YAML/缓存，全部生成落盘经ArtifactStore.cache，不伪造正式Plan。Windows本机动态no-replace与真实多进程竞争/错误/既有空目录/文件/junction，Linux仅未测分支如实披露，未知平台fail closed；发布helper拆cache_publish；不改C1原API规则，不新增tests/unit/io/__init__.py。关键输入全域tau、最小次正规数/负零编码，cache最长116，完整hash参数绑定，零C(H)/HMAX临界、Shanghai当地20–08首[144,288)、深层immutable、strict canonical/reference/每台capacity、默认YAML漂移都按计划。
保持简单清晰、文件150–300/函数20–60参考，不压缩凑行数，不长文件；有需要超范围先报root/temp规划，不擅自新增模块。完整测试基线保留，新增skip/xfail禁止，Hypothesis不引入，golden常量你不写。uv run --python3.11 --group dev python tools/check.py及规定定向检查（实际命令使用 --python 3.11）。必要检查通过就交付，不无限重复测试。完成全部G2及handoff（文件用途、命令和实际结果、依赖与平台来源/未核实/限制、实际模型、行数表、三组回归hash供reviewer独立核对）后消息root；不要在只是初稿时宣称DONE。独立review将另行派发。
```
