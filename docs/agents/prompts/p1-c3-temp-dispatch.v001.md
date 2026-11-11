# P1-C3 temp 实际派发 v001

模型gpt-6.1-terra；reasoning_effort=high；fork_turns=none。角色：临时planner/prompt-engineer，明确不是Claude。
绝对仓库D:/Default/Replan-mutil agent。没有先前上下文，以下事实及指定的仓库文件为全部上下文。

用户最新明确“继续，claude额度用完了就换temp智能体”，覆盖刚才Claude恢复后temp退出的历史状态。Claude消息88完整生成后已额度耗尽，页面提示14:40恢复；不保证该时点可用，不升级。你现在替代其计划角色，保持G0–G5。root必须审G1 PASS后才派专项；你不得实施或自行派实施，不提交推送、不改Git。

实际Git：集成codex/p0-governance，本地及远端43b19a42b853fa89878b5f08ab930b4c427c71c3，main40cdafd47c66d3dd075d16a81d004eee088b97ab保持。C2源码cab8873已G3/G5 ACCEPTED，721 passed/1既有symlink权限skip、68文件静态全部通过；本轮verify_source全文/分批PASS。root正在单写授权/进度等文档，不能把这些当你的范围。下一个包为P1-C3清理与归档，原Claude完整初版在docs/work-packages/p1-c3-claude-initial.md，根本不需重做C2，也不做P2/前后端/make_report。B1位置与solver配置仍DEFERRED。

先阅读AGENTS.md、docs/progress/PROGRESS.md、docs/agents/RESUME.md、registry.md、model-policy.md、temp-planner.md、planner.md、prompt-engineer.md及公共提示词前言；docs/engineering/coding-standards.md、file-storage-standard.md、review-gates.md、open-source-policy.md、git-workflow.md；p1-c3.md和Claude初版。核对源码io/artifacts.py、manifest.py、paths.py、cache_publish.py、errors.py、tools/check.py、layout_rules.toml、check_import_boundaries.py及既有tests/unit/io约束。只读核对原文spec第2.6/2.7/6节P1、相关设计原文及manifest，先运行python tools/verify_source.py。不得改原文。

目标：完成原P1-C3规划与提示词，解决root G1 REWORK，不改变原业务规则，给root可直接审查派发的完整冻结版本。可引用Claude初版为历史来源，但必须明确哪些是temp的新决定，不冒称Claude批准。无需询问用户工程字段/接口选择。

root G1主要问题：原verify承诺内部一致性，prompt却写sidecar字段被改均失败。合法archived_at变化不被zip/hash覆盖；没有外部可信锚不能检出所有元数据变化，也不能检出zip和sidecar同时自洽修改。请明确严格格式/身份与zip内原manifest/Git字段/内容的对应校验；empty_directories等仅侧文件字段的可验证边界；必须拒绝与可能通过的正反验收。不得引入签名系统、外部服务或依赖来回避。可提出更简化而完整的标准库实现，但不能私自改变保留规则。

补齐实施可落地细节：ArtifactStore.root已公开；路径守卫在io/paths中可包内复用，原_is_link已在同包使用，不必无故改C1。所有机器产物需ArtifactStore语义入口，dry-run不创建root；请选择明确简洁公开API和归属，不能偷偷将整个维护绕过既有存储约束。cache_publish现docstring为目录，不盲承诺普通文件支持；需要在实施前验证合法普通文件不覆盖语义。归档两文件发布失败、回滚归属、并发目标不覆盖、只读权限失败需有实质测试；限制无TOCTOU和Linux未动态测试应如实披露。INDEX保护应保守，不能漏规范完整run_id或规范路径，格式歧义/不可读时fail-closed，能明确无需过度抽象即可。不得为“全部篡改必检出”造不真实保证。

清理默认dry-run；tmp7d、failed/partial14d；running只报告不删除（工程规范明确拒绝正在运行）；completed不删，归档源保留，论文未定稿不对真实产物apply。仅tmp_path/系统临时构造数据测试apply，不碰真实artifacts。失败/中断源manifest损坏fail-closed；子树链接/junction/hardlink/特殊文件拒绝，删除只作用于验证绝对目标，不跨shell，不递归改目标外权限。输出绝对路径/依据/大小/引用；显式apply。归档不覆盖，无解压功能，无报告复制。

原初版5个io模块可能过大，请在规划阶段按实际职责明确必要辅助文件与测试helper，保持简单完整、可读，不造框架。函数20–60/文件150–300是审查参考，不凑行数。对模块边界确有需要的拆分现在给精确文件名，不让作者自行扩大。每阶段定向检查，最终完整check，不无变化机械重跑全量。不得新增skip/xfail或削弱旧断言。tests/unit/io不新建__init__.py；tests/unit/tools按实际需要精确列明。root单写p1-c3卡片、进度、CHANGELOG、RESUME、registry、提示词；作者只写限定源码/测试/用法说明及自身handoff。独立review只写自身handoff，作者与review必须不同会话，均Terra/high/fork none。

只允许写：
1 docs/work-packages/p1-c3-temp-plan.v001.md
2 docs/agents/handoffs/p1-c3-temp.md
其他全部只读，不修改公共角色文件、Claude归档、源码/测试/依赖或Git。你可运行只读检查/临时探针但不得生成仓库业务产物。

交付内容：来源与授权、相对Claude初版的完整决策Δ、完整合并契约（不要求实施者自己拼冲突版本）、明确公共API/文件职责、精确写入白名单和root/作者/review互斥；可直接派发的实施prompt和独立G3 prompt（完整参数/背景/必读/验收/命令/范围/禁止/交接）、G1检查清单、剩余限制。完整验收保持原初版全部有意义反例并修正无法实现承诺，新增内容要说明理由。需要用户改变业务规则/研究范围/既定目标时仅报告并保留其余独立规划，不自行裁决。

结束记录真实模型配置、读过的原文与源码、执行命令/结果、文件用途；不要写G1已通过或C3已实现。root审G1后才实施。
