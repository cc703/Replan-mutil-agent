# P1-C3 独立 G3 实际派发 v001

配置gpt-6.1-terra/reasoning_effort=high/fork_turns=none。角色未参与实现的独立reviewer，绝对仓库D:/Default/Replan-mutil agent，不读取作者会话；仅磁盘交接与源码。只写docs/agents/handoffs/p1-c3-review.md，其他全部只读，不修复/提交/推送/改Git。探针和CLI只用系统临时目录，不触碰真实artifacts，Windows删除/移动前验证绝对目标位于该临时root，不跨shell删除。

背景：用户继续P1，Claude额度不足由temp按显式授权提供计划。C2验收已同步；C3方案是docs/work-packages/p1-c3-temp-plan.v001.md+卡片末root G1最终复核，当前初版Claude历史语句不能覆盖已修正契约。temp不参与实现与本审查。读AGENTS、PROGRESS、RESUME、模型策略、reviewer、公共前言（历史冲突以当前授权为准）、相关工程规范、原文manifest。先核原文。完整读temp计划测试清单、root G1、两份实施派发，以及p1-c3.md/p1-c3-archive.md作者交接。基线HEAD43b19a4，721 passed/1原symlink权限skip、68file静态；实际G2总数以最终交接和root复核为准。

范围：按两份实际派发白名单逐文件核diff及未跟踪文件，root治理文档归root，源码只有新增维护/树/清理/归档与artifacts两个新入口；无旧契约/旧断言修改、无依赖/锁变化、无skip/xfail、新init或新framework。条件变化若未root批准必须REWORK。代码清晰职责、类型、公共API docstrings完整；大文件需实质职责理由，不能压缩排版。

从独立角度执行有意义边界，不只复跑作者测试：
1 原文/布局/依赖导入检查，ArtifactStore.open_existing/maintenance保持旧行为；非法或缺root/盘根/项目marker/dangling marker/原始junction/..路径拒绝且不创建目录；所有IO新模块保持既有依赖约束。传入伪造plan不能越过绑定store的候选或归档路径。
2 tmp年龄用os.utime(ns=)，独立核递归最大值、恰边界不合格/多1ns合格、未来、空tmp/缺tmp；failed/partial只依ended_at且14d下限，running不删且stale仅报告，completed不候选，损坏manifest/坏名/特殊文件/links/junction/hardlinksfailclosed。
3 INDEX至少12种独立内容probe：完整ID表格/代码/链接/反斜杠路径、名称级保护、兄弟与前缀过保护、缺失、BOM/CRLF、NUL/非UTF8/超限/目录/junction、不规范或截断token/百分号/片段/查询。按冻结机械规则failclosed，保护和无删除证据真实；不保证识别没有完整ID或规范路径的口头缩写。
4 dry-run（清理/归档/verify）前后独立树快照bytes/mode/mtime/类型/路径相等；CLI不创建root/tmp/archive。apply重新推导目标并逐目标重验，计划后新增、状态变化、INDEX变化、注入junction跳过/拒绝；root外哨兵及权限不变。Windows readonly删除、部分失败报告剩余、其他候选继续、0/2/3/4退出码。剩余路径遍历不能跟随失败后新出现的junction，不rmtree或跨shell。
5 archive仅completed，canonical ZIP名字/排序/固定时间权限/大小/内容sha逐项独立重算；source_manifest_sha256必须等zip内原manifest原字节，Git/身份/status/config hash/outputs对应。ArchiveRecord重复键/额外字段/严格类型/非法路径拒绝。empty_directories仅侧文件结构记录，archived_at仅UTC合法性；合法元数据变化和整套自洽重写可能通过，不能宣称防篡改。测试既必须拒绝又可通过的边界。
6 verify无需磁盘源run存在且不解压；zip重复/多余/缺失/不规范成员、截断/篡改、不一致sidecar/manifest拒绝。只依内部hash不是可信原始来源证明。
7 Windows普通文件no-replace真实独立probe；目标存在三组合、发布前竞争都不能覆盖。两stage读回/源变化、zip写失败、verify失败、第二发布失败、身份变更回滚拒绝、回滚失败partial和chmod只读告警都有实际探针。工具不写源；SOURCE_CHANGED注入外部修改不要求工具恢复，不能伪称绝对源不变。
8 README/存储规范/Makefile与实际CLI行为和限制一致，Makefile默认dry-run，无新业务/阶段或真实实验结果。

必要定向测试后完整uv run --python 3.11 --group dev python tools/check.py；git diff --check；来源/布局/导入/静态均须实际通过，旧测试不降、skip仍仅原Windows权限skip。无变化不机械重复全量。若故障注入与作者套件重复，只重跑覆盖独立风险的最小必要集合；具体结果如实记录，未测不写PASS。

结论ACCEPT/REWORK/ESCALATE；逐发现严重度、文件:行、证据、建议；独立探针真实输出和所有命令/测试数、限制与未核实项、文件用途及实际模型派发参数。只有完成本包所有必要审查才能ACCEPT，不能把作者自检当独立证据。发现问题只写handoff/通知root，不改作者源码。

实际G2补充：root完整check已执行836 passed/1既有symlink权限skip，90file ruff/format/mypy、layout/import/source全部PASS；两作者已停写。root补齐README归档用法和存储规范边界，白名单内。请从此稳定磁盘状态独立审查；共享socket/符号链接与超限通过真实可用探针或明确替身解释，不把未实际构造十万文件当已构造。verify对不可信ZIP格式损坏、压缩流/不支持方法异常应检查是否安全映射为拒绝，而非漏到CLI traceback；属于输入边界，不要求扩展功能。
