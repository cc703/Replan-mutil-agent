# P6 G3 独立审查（进行中）

基线 72930d72；审查者 Terra/high/fork none，独立于实施。当前结论 REWORK，复验未完成。原文 verify_source 全 PASS。已读工作包全部合同、作者交接、原始 §7 与 spec P6/D1/D7，抽查核心验证上下文、现有代码和测试。未运行全仓及在线付费请求。

## 阻断

1. graph.select 原先以 `explain(facts, lambda: [])` 固定降级，缺实际模型解释、受控重试和完整证据包。
2. START 依赖外部 action 默认 change，route 提示未使用，模型工具建议未连通；CLI 强制离线并固定话语和回复，无自由输入或线上启动入口，不满足原完整自然语言链路。
3. evaluation.prediction 单条 IR，实际 schema 是 changes 数组；七类样例缺话语输入、相对时间、多条与缺参。独立探针相同有效 outage 单项匹配，包在 changes 后判 clarification。未同生产路径做完整语义抽取评测。
4. urgent IR 直接暴露核心槽值，回译未转换嵌套任务截止/释放/工期；需外部绝对带时区时间、明确单位及 TimeAxis 精确转换。
5. rollback 以历史 evidence 原 base/free/context 验证，而非可信当前运行状态。微型探针 p 的 t=1–3、合法 q 的 t=5–7，当前快照记录 q 的任务运行中；独立 validate(p, base=q, free=set(), current context) 报 V10/V11，而 L2 rollback 接受 p。注意本探针 q 经私有 _add_candidate 注入，尚未证明相同 q 通过公开求解路径可达；但公开 rollback 不接当前上下文，图传入的当前 context 也不参与判断。需针对可达实时情景复验。

## 独立探针

PowerShell `$env:PYTHONPATH='src;tests/unit/agent'` 配合 `uv run --locked --python 3.11 python -`，使用 test_store.make_world 创建两个 session，回滚许可跨会话、伪造、重放均 PermissionError，修订分别保持 0、0、1。模型包装评分反例如上。以上为代表性验证，非穷尽证明。

## 待复验

作者返工后检查真实图模型调用及脱敏、确认前后、冻结/授权/候选与回滚、UNKNOWN/协商、评测完整语义和两 CLI；检查依赖与范围。未核完项不作通过声明。root 负责 G4/G5 和统一检查。

## 返工复验 2026-11-17（待再次返工）

- 图已接入模型解释及有界重试、自然语言路由/聊天入口、急件外部绝对时间。首次回滚问题已加入 current context/base 及缺快照拒绝；模拟运行中状态代表例尚非公开演进证明。
- 独立真实图停机求解：L1 前 revision 0，批准后 L2 前 revision 1，独立 validate 4 次；L2 后 revision 2、另调用 3 次。
- 仍 REWORK：在线抽取无实体清单、业务 now 或别名，唯一别名 resolved_id=null 的可信语义层不会补解析；实际 usage 丢弃、trace 节点 token 恒 null；解释输入未包含完整差异和诊断/松弛证据。已交 root 安排补齐。
- 评测另有独立反例：互换两句 gold，逐句 exact 均 0，而跨句汇总匹配 2/2、F1 1.0；同一时间不同偏移表示如 00:25Z 和 08:25+08，错误 F1 0。应按句汇总且统一绝对时刻比较。探针文件在忽略的 artifacts/tmp。

## 最终复验 2026-11-17：ACCEPT

上述 REWORK 项经本轮返工关闭。此结论仅为 P6 G3；G4 许可和全仓 G5 由 root 完成。依工作包核验设计 §5.5/§7、spec P6/D1/D7、P5 核心接口、原始哈希、相关实现/交接及工作区范围；未修改源码、旧测试、Git 配置或提交。

独立验证（均为根目录 PowerShell，设置 `PYTHONPATH=src;tests/unit/agent`、`PYTHONUTF8=1` 后使用 `uv run --locked --python 3.11 python -` 的内联探针）：

- 注入本地模型传输替身、真实图与微型 CP-SAT：依次 route、extract、L1、solve、explain、L2；唯一别名 machine→d 在模型 resolved_id 为 null 时得到可信解析，抽取请求携带设备/任务、别名、时间轴和业务 now。每次模型调用分别记录总/输入/输出 token 12/8/4、三种提示哈希。ArtifactStore 产物 manifest 标记 offline、dirty、模型及版本；检索产出文件不含注入密钥、请求原文及别名哨兵。
- 有影响的停机迫使任务 1–3 移至 3–5；解释器确收到前后设备、人员、起止、结束变化、影响原因和候选指标，单位与结果一致。不可行截止例经真实图进入协商，收到核、代价和延后证据；注入三次虚假数值触发模板，虚假数值未展示。UNKNOWN 分支及许可边界见此前探针及审查。
- 上轮互换两条金标探针重跑：总体 F1 从 1 降到 0；同一 UTC 与上海时刻得到 F1 1。检查单句内匹配、三次离线评分和类别分母，录制响应独立于 gold；这不构成 DeepSeek 准确率评估。
- 已观察真实图停机的展示和提交再次独立验证；跨会话、伪造和重放拒绝。当前回滚使用当前父计划、快照及 free，缺事实拒绝；运行中快照的反例通过模拟可信运行状态构造，未证明该状态可经公开业务入口完整演进。

限制：未使用付费在线服务，模型 ID 可用性、真实 API、时延和费用未实测；checkpoint、会话及审计仅在进程内，进程重启不恢复。真人标注的正式 D7/E6 数据与评估未执行。本审查未重复全仓检查，root 负责集成和同步；G3 不代表 G5 已通过。

## G5 导入修正核查

静态核查 `test_llm.py:10`、`test_graph.py:12`、`test_explain.py:4` 均使用 `from tests.unit.agent.test_store import make_world`；G3 ACCEPT 不变。三个测试文件尚未跟踪，Git 无修改前快照可供独立逐行比较，故“仅改导入、断言未改”依据作者交接，未独立证明。root 报告全仓 mypy 199 文件通过；此处未重复运行。
