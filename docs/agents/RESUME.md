# 跨会话恢复清单

2026-11-11最新：C2已G5同步，最新已核验HEAD08793cd0eac04f673c944cc495a08b195995c2ab，cc703认证、chm作者，main保持原SHA。下一包P1-C3清理/归档已取得Claude消息88完整计划与两份prompt，归档work-packages/p1-c3-claude-initial.md；root G1 REWORK（FAIL）：verify内部一致性与“任意sidecar字段修改均检出”的验收承诺不一致，需最小Δ澄清。Claude随后额度耗尽、提示14:40恢复；未再发送/升级，temp不接新规划。无C3源码专项或源码/依赖改动；不绕过G1。恢复先读p1-c3.md审查及待发请求，Claude修订→root G1→Terra/high/fork none实施与独立G3。超期running按既有存储规范只报告；不进入P2/前后端。

2026-11-11 G5同步已完成：Git使用现有Windows代理后恢复连接，实际Git凭证经GitHub /user核验为cc703；作者chm。源码提交cab8873902c6fa9c1c8cd743abbaf434b54a2c46及状态提交9adedb28497aba36933aeb31c3891b7cf157b038已普通推送至origin/codex/p0-governance，ls-remote与本地HEAD逐字一致；main仍40cdafd47c66d3dd075d16a81d004eee088b97ab。无强推、无历史改写。C2为ACCEPTED，G0/G1/G2/G3/G5 PASS，G4许可已批准；最终工程证据721 passed/1既有skip、68文件静态通过。后续按原顺序请求Claude提供P1清理/归档包计划，经G1后派发，不进入P2或前后端。此前失败及中间状态均为历史。

## 当前续作入口（2026-11-10）

2026-11-11 G5恢复点：本地C2源码cab8873902c6fa9c1c8cd743abbaf434b54a2c46已commit，chm作者；Claude已接回、temp退出新规划，G3 ACCEPT/721+1/68静态已通过。普通push失败（github.com:443直连超时，无Git/环境代理），用户连接信息请求待答；不重复开发或改写提交。连接恢复后只用cc703认证（本机尚缺该凭证），普通push现有codex/p0-governance并ls-remote核SHA，成功后再标ACCEPTED和请求Claude下一清理归档包。不得把本地提交或连接插件账号当已同步。

2026-11-11最新：Claude已接回，C2收尾独立G3 ACCEPT，三组回归锁root已冻结；最终完整check721passed/1原symlink skip、68file全静态与来源/布局/导入通过。当前G5准备提交/同步，cc703本机CLI凭证尚缺（GCM仅其他账号，未使用），不要把插件cc703身份当本机push已成功；实际Git为准。未启动清理/归档或P2，新包继续Claude。下方为各阶段历史恢复记录。

2026-11-11最新覆盖：用户要求“继续，回到与claude执行合作的模式”。已重新打开原Claude会话并提交temp v001/v002决定与C2收尾交接，temp停止新规划。本机实际旧子智能体句柄已缺失（list_agents仅root），不得假定昨日最后一次followup已执行。磁盘assign_times仍原地修改tasks/persons；需Claude收尾增量→rootG1→同模型新实施/独立复审恢复。已有717+1全check是修正前证据，G3 REWORK文档已补但未复审；本包未提交推送。

当前执行：已获Claude消息86、root G1通过（work-packages/p1-c2-claude-closeout.md）；实际/root/c2_closeout Terra/high/fork none正在修指定四文件，别重复spawn或覆盖。完成后新独立G3复审，原大矩阵证据保留只做必要回归。temp已退出，后续规划继续Claude。

最新执行：收尾已G2完成，718passed/1原skip、67file静态，9hash相同，root135样本差分一致。实际/root/c2_closeout_review已spawn并正在独立复审，禁止并行改被审源码。仅其review交接最终结论可作为G3证据；G5未提交推送。

最新用户覆盖额度停线条件：已明确授权创建temp代Claude完成计划与提示词，流程不变，额度恢复后再交回Claude。已spawn/root/temp，Terra/high/fork none；仅写p1-c2-temp-plan.v001.md及handoffs/temp-planner.md，root负责G1审查。看temp-planner.md与prompts/p1-c2-temp-dispatch.v001.md。原文/Claude历史计划不改，实施尚未开始。

当前执行已推进：temp v001经root G1 PASS，实际/root/p1c2_implementation（Terra/high/fork none）已启动G2；完整范围和实际载荷见prompts/p1-c2-implementation-dispatch.v001.md及主prompt。恢复先检查专项真实状态与其磁盘交接，不重复spawn；当前仅本实施者写源码/依赖/测试，root不覆盖。独立G3仍待派发，不能将中间通过数当完成。

当前G2已并行切分，旧“仅一个实施者”是切分前历史：IO/配置/依赖方/root/p1c2_implementation，生成器源码及生成测试方/root/p1c2_generation，均Terra/high/fork none；原作者已确认停写generation，四草稿由生成方接管。双方交接分别p1-c2.md与p1-c2-generation.md，完整派发见prompts对应日志。用户NumPy许可G4已解决（ADR0007）；真实依赖安装/API及mypy小探针已过，完整业务G2尚未完成。

C2 G1 v002已通过：为保留既有C1存储依赖断言，业务缓存编排改为顶层scheduler_core.instance_cache，删除未发布旧IO路径、无兼容wrapper。原IO作者按temp v002与root实际prompts/p1-c2-location-dispatch.v002.md迁移；原prompt历史不改。生成199定向通过但G1所需反例覆盖仍补齐，不可把它们转嫁G3或提前验收。

当前联合G2已最终PASS：root完整check717passed/1既有skip、67文件全静态与来源/布局/导入通过。生成与IO两作者已交接稳定；独立/root/p1c2_review（Terra/high/fork none）已实际spawn，完整派发prompts/p1-c2-review-dispatch.v001.md，只写review交接。恢复先核真实专项状态，不重复spawn、不擅自改被审代码；G3尚未结论、G5未做。

最新用户已恢复开发，覆盖下方历史 C1 暂停。当前 P1-C2 规划中：恢复基线 0d5b394 本地远端一致；完整检查 250 passed/1 原 skip、40 文件静态与来源/布局/导入通过。原Claude会话消息82完整初版与84完整Δ已归档（work-packages/p1-c2-claude-initial.md、p1-c2-claude-delta.md），G1 PENDING，四项一致性见p1-c2.md末。Claude额度已用尽，页面提示20:50恢复；按既有条件停依赖实施，无升级/新消息。专项未派发、无源码/依赖改动，仅root未提交规划文档。恢复先读卡片→初版→Δ→G1发现，再向Claude请求最小补齐。浏览器曾读取超时，公开tabs.get+playwright.domSnapshot可读；超时先观察避免重复发送。会话已markHandoff。

当前C1已G2/G3完成，独立ACCEPT，250 passed/1原skip、40文件静态/来源/布局全部通过。六io模块与四测试已落盘；交接handoffs/p1-c1.md、p1-c1-review.md。完整计划初版→Δ→root G1在work-packages/p1-c1.md，实际Terra/high/fork none作者及reviewer用量中断后同模型恢复完成，无降级。G5已完成，dba733d已推送核验；干净提交上的真实c1_smoke运行completed、dirty=false且跨Run写拒绝。本轮按用户要求暂停，不开启C2/清理/前后端。以PROGRESS、真实Git与磁盘为准。

用户已恢复开发，最新强调简单完整、目录清楚、文件可读；覆盖上一轮暂停。基线799ea56已同步，P1-B原业务交付1255113已ACCEPTED。当前实施P1-B-R1行为不变重构：工作包p1-b-r1.md含外部Claude76与root G1；实际/root/p1br1_code_terra，Terra/high/fork none，完整载荷在prompts/p1-dispatch-log.v001.md最前。先迁测试再拆源码，保持162通过/原1skip、61reason和5829oracle，API/报告/异常新旧差分一致。

源码仅薄入口与validation下六实现模块；测试按规则族迁移，删除旧巨型test_validate.py为本包授权；models/axis/validation_context/依赖/锁/工具/mini/原文只读。当前G2/G3最终已PASS，独立ACCEPT，唯一纯区间职责返工闭环；G5已完成，正式提交ead0c62087e933748a824426f32c37676c4d230b已普通推送核验一致。源入口67行，六模块最大190行；6044全量差分与35独立边界一致、162 passed/1原skip。实施/独立交接见handoffs/p1-b-r1.md与p1-b-r1-review.md。后续先C1 ArtifactStore与manifest，再C2生成器，需对应Claude完整计划；仍不跨P1。用户仅询问原顺序工期，尚未批准阶段调整，继续先C1/C2，不提前做网页。Claude若额度耗尽按用户条件停止，不升级或绕过。GitHub仅cc703/作者chm，普通push且SHA核验，保留main演示。

## 通用恢复步骤

1. 阅读根 AGENTS.md、进度 PROGRESS.md、工程规范、门禁、角色索引、模型策略、工作包卡片、Claude 完整计划与派发提示词、最近交接；按需阅读已核验的设计原文与勘误。
2. 在仓库根目录运行 `git status --short` 看未提交改动，`git log --oneline -n 10` 核对本地提交；运行 `python tools/check_repo_layout.py`，PASS 才为布局通过；运行 `python -m pytest tests/governance -q`，看退出码与测试数；SOURCE 合入后运行 `python tools/verify_source.py`，退出码 0 才为核验通过。未就绪不等于通过。检查变动所属工作包，不覆盖他人工作。
3. 状态以 PROGRESS、工作包、门禁证据与实际 Git 状态综合判断；本地提交不代表同步。R2 需总设计师确认 SOURCE G3 通过，并先复跑源文件校验。
4. 重新派发先取得本包 Claude 计划、完整提示词及 G1；当前 [Claude v001](../work-packages/continuation-claude-v001.md) 第 2、3、4 节为本轮原始提示词来源，P0 实际派发见 [审查记录](../work-packages/p0-claude-review.md)。逐字摘录及来源哈希见 `docs/agents/prompts/`；实际派发调整另见 R2 交接。按模型策略设置并提供自包含上下文、绝对目录、写入范围与验收；不得假设旧会话仍在运行。
5. 待裁决事项见 [讨论](../planning/open-discussions.md) 与 ADR；B1 和 solver 建议保持延期。专项禁止改写原文、扩大范围、提前实施业务或自行提交推送、改Git配置；总设计师按当前用户授权执行普通同步。
6. 恢复外部 Claude 时提供 AGENTS、进度、相关工作包、审查记录、三份原文与全文哈希、逐 200 行批次哈希清单、勘误和用户裁决。原文可经已验证整文件 Copy 加全文哈希传递，仍逐批核对；缺失或不匹配不得声称核验。

本轮 SOURCE G3 已 ACCEPT，见 [SOURCE 交接](handoffs/source-g3.md)；本地 checkpoint `5dbcdee`，未推送。恢复时仍须复核当前状态。
