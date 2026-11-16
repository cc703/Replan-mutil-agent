# P3 契约与订阅事务增量方案 v001

来源：temp（Claude 额度不可用期间按用户授权代行，非 Claude 输出）；2026-11-16。状态：待 root G1；本文件不授权实施，不修改既有 Claude 计划来源。输入：AGENTS.md、p3.md、p3-claude-plan.v001.md、P1 validation/index.py、execution.py、validation_context.py 及 P3 simulator 实际实现。原计划 U4 已要求未开工不自动补开、触发重排；原 spec 对 start<now 推定冻结，本方案以明确执行事实覆盖该推定，是有条件的契约语义细化，交 root 判断是否属于既授权 U4 或须用户裁决；不得当成单纯字段改名。RUNNING/DONE 的冻结不变。若 G1 未解决授权与范围则暂停相关实现。

## 问题与目标

P3 默认 flush 在阻塞后一槽，P1 index 以基准 start<now 冻结 SCHEDULED，因此实际未开工任务无法移动。P3 快照仅涵盖 RUNNING/DONE，batch 会清空，不能证明当前未开工。另 engine 每个有订阅的事件全量 deepcopy 实例状态，规模随实例增长；要求事件失败恢复且支持回调重入，不以关闭订阅或禁用重入掩盖问题。

## 证据和接口

新增严格结构化 NotStartedEvidence（名字可依项目风格）：task_id、base_plan_id、planned_device_id、planned_start、planned_end、planned_person_id、blocked_at、event_id；纳入 ValidationContext 的默认空列表。snapshot 为必需且绑定同一 base.id、as_of=inst.now；每项唯一，任务存在且状态 PENDING/SCHEDULED、base assignment 各字段完全匹配，blocked_at 不晚于 now 且不早于 base_as_of，event_id 非空；同时不得有该任务 RUNNING/DONE execution record。无效、重复、错基准、未来、冲突、无快照均产生明确违规并使报告失败，不因证据非法而放宽冻结。校验器验证结构与一致性，不声称证明外部事件真实性；真实事实由调用方负责。对于有效证据仅取消旧 start<now 的推定，RUNNING/DONE 始终冻结；缺证据完全保留原行为。仍执行全部既有约束及候选开始不早于 now 的规则，free 与父计划契约不放宽。注意 snapshot 缺 base_as_of 时证据不可用，不能猜测。

仿真器在真实 SETUP_START 或 TASK_START 阻塞时记录事件身份和对应当前 assignment；实际运行、完成或该任务 assignment 发生变化即撤销。成功采纳新 base 时，对 assignment 未变且依然未开工的记录以仿真器实时状态重绑定新 base 和采纳时刻：保留原阻塞事件时间另设 observed_at=新 base_as_of，证明它在新基准时仍未开始；此处证据结构增加 observed_at，并要求 blocked_at <= observed_at <= snapshot.as_of、observed_at >= base_as_of。不能仅把旧事件直接改 base id；只有引擎自身运行态确认且无任务开始才可重绑定。失败、重试或窗口放弃不删除事实；后续触发仍能提供。任务开始、完成、被替换、取消或被重排即撤销，新的阻塞产生新事实；事务回滚恢复该表。回放由相同事件与状态机重建，校验结果和日志确定。SETUP 阻塞只证明任务未开始，不将准备资源当作运行占用；现存 setup 清理行为保持。

保留旧三参数 Scheduler 和现有 Simulator 调用；新增显式可选四参数上下文回调入口（例如仅 keyword scheduler_with_context，调用方二选一，禁止通过捕获 TypeError 猜签名），上下文是调用前独立深拷贝，先构建一次证据快照并传给该回调；候选验证基于同一不可被回调改写的内部快照，再补充依候选产生的 end_changes。老回调继续工作且可返回结果，门禁仍使用内部证据；需自行识别冻结集合的调度器应迁移新入口，P4 对接记录。不得把证据仅藏在事件列表或修改 Instance 时间、伪造任务状态/基准计划来规避 V8。超时派生验证也使用同一有效未开始事实。候选必须 parent=base，其他 L1/L2 语义不变。

## 订阅事务

采用事件级增量撤销日志与现有嵌套 queue journal：每层事件开始建立 journal，所有可能变更在首次写前记录旧值或追加操作的逆操作；覆盖 clock/current、instance/task及索引、plan/base、运行和准备集合及计数、设备状态、故障窗口和索引、触发窗口、epochs、随机/回放游标、生成集、统计、历史长度及新证据等。不可仅浅拷贝可变嵌套对象；记录原引用时必须采用写时复制或独立旧值。入队/出队、失效计数与序号由 queue 嵌套事务处理。正常提交内层时合并逆操作到父层，外层失败能撤销已成功的重入；内层失败只回滚内层，异常若被回调捕获则外层可继续。回调允许调用公开注入、订阅、查询及嵌套 run；订阅列表变动也纳入事务，按调用开始时的订阅快照通知，避免迭代中新增造成重复/无限通知。明确线程并发不在范围。重入 run 的事件、history、队列和 clock 随父事务一起回滚；外部回调自身 I/O 和用户对象副作用无法撤销，应文档说明。SchedulerFailure 和 ListenerFailure 原异常传播及各自现有事务语义保持，不能回滚已经在本事件之前提交的事件。任意异常路径必须平衡 journal 栈。无订阅仍走现有轻量路径；有订阅的正常事件不得全量复制实例、计划、队列或历史；成本按实际写入量计，失败回滚允许按修改量工作。允许输入输出隔离所需局部拷贝，不许通过全量序列化替代 deepcopy。

## 写入白名单及交付

实施仅限：src/scheduler_core/validation_context.py、src/scheduler_core/validation/index.py、src/scheduler_core/validation/execution.py、src/scheduler_core/validate.py（如需接线）；src/simulator/{engine.py,runtime.py,gate.py,trigger.py,queue.py,replay.py}、必要的新 src/simulator/transaction.py；tests/unit/validation/ 下相关测试、tests/unit/test_validation_context.py、现有 simulator 测试目录及其测试辅助；docs/work-packages/p3.md 中追加接口细化及 docs/agents/handoffs/p3-contract-implementation.md。新增测试文件限上述测试目录。其他模型、求解器、依赖、配置、设计原文、全局治理及已有无关修改不得写。若必须改其他文件先向 root 报告扩范围，不擅自执行。root 单独负责进度、派发记录和 Git。具体测试目录以 rg --files 发现为准；不新建平行目录。

## 实施提示词

你是 P3 契约增量实施专项，模型 gpt-6.1-terra/high/fork_turns=none；先读 AGENTS、P3 卡、P3 Claude 计划、本文件及当前相关源码；执行来源校验。只在上述白名单内实施，先确认 root G1 已明确放行本版本及业务授权判断。依据本方案落地证据、回调兼容、完整生命周期和增量事务；不改业务规则以外的其他功能，不修改设计原文，不提交推送。对于无法在范围内安全实现的事务变更，保留现场并报告，不静默限制重入。添加有意义测试，实际运行定向和项目完整检查，交接记录文件、命令、结果、复杂度证据、限制和失败路径；不得声称 G3 通过。若发现 P3 作者并发修改，先与 root 协调文件所有权，不覆盖其工作。

## 独立 G3 提示词

你是独立审查专项，模型 gpt-6.1-terra/high/fork_turns=none；只读审查实现，报告写 docs/agents/handoffs/p3-contract-review.md，不改作者文件、不提交。独立构造并实际运行：阻塞后默认延迟 flush 的合法候选被采纳及后续真正开工；setup 与 start 阻塞、容量与不可用、失败重试/放弃后新触发、其他任务变更导致基准更新、该任务重排/开始失效、多个连续基准、回放一致。分别测缺证据原行为、伪造 RUNNING/DONE、快照过期、错误 base/assignment/时间、重复/未知/冲突证据均拒绝；旧三参数及新四参数回调均工作，修改回调入参不影响门禁；其余 V1–V11 与父计划约束不退化。订阅事务覆盖 status/event 回调分别抛错，注入后抛错、嵌套 run 成功后外层失败、内层失败被捕获后继续、订阅增删、队列 epoch/seq/日志/统计/证据恢复，重试与无异常对照逐字段及日志一致；验证回调外部副作用限制。用可重复探针证明有订阅单事件正常路径不按未触及任务数量复制全量状态（例如对全量复制入口设失败探针并检查大实例），不是仅测运行时间。检查队列事务嵌套、所有修改点及异常栈平衡；运行必要测试和完整检查，给 ACCEPT/REWORK/ESCALATE 与具体定位、命令、证据、范围和剩余风险。授权未决不得 ACCEPT。
