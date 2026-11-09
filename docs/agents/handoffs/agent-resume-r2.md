# AGENT-RESUME R2 交接

- 状态 DONE，待总设计师 G3；本次实施 `/root/resume_terra`，模型 GPT-6.1 Terra / high。SOURCE G3 由 `/root/review_terra` 独立 ACCEPT，见 [SOURCE 证据](source-g3.md)。checkpoint 5dbcdee 仅本地，未 push。
- 新增 prompts 七份：P0 前言及 A/B/C、公共增量、SOURCE、RESUME 的 Claude 原文摘录；每份文件头记录来源路径、行范围、全文与摘录 SHA256。新建 P0 A/B/C 证据交接与 SOURCE 索引；原始 P0 专项交接及模型未记录，不假造。新增 P1 readiness，含 21 模型与两个别名的问题、逐行引用、阶段依赖、候选文件、验收和阻塞选项。更新 registry、RESUME、README（仅追加）、工作包、讨论；不写业务或原文。
- 来源层次：上述为 Claude 原文逐字摘录；实际 P0 派发与审查调整见 `docs/work-packages/p0-claude-review.md`。本次实际派发由总设计师补充：整文件 Copy 并核验全文与分段；独立 reviewer 与总设计师分离；SOURCE G3 后 R2；实际会话及模型策略；源码保护和写入边界；以上调整不是 Claude 原文，具体以工作包及本交接为准。模型覆盖需 `fork_turns=none` 和自包含提示词。
- 真实验证：开始运行 `python tools/verify_source.py` 退出 0，三份全文及14块全部 PASS；`uv run --python 3.11 --group dev python tools/check.py` 退出 0，布局、依赖边界、来源、ruff 检查及格式、mypy 全通过，33 passed、1 skipped in 8.15s；跳过原因是系统无法创建符号链接。七份提示词按来源字节切片及头部两个哈希全部 PASS。第一次临时比对脚本因 Python bytes 字面量含非 ASCII 而 SyntaxError；修正脚本后七份全通过。验证在文档最终少量更新前执行，需总设计师最终复核。
- 用户方向裁决 D-003：保留 V7、下一步提出人员契约提案；具体字段和接口未批准，不得据此实现或冻结。B1 与双 profile 仍 DEFERRED-BY-USER。P1 其余关键问题见 readiness：容量/V2/V9、时间舍入、运行中超时及冻结/V10、NEGOTIABLE、初始求解 None 歧义、P1/P2 验收边界。
- 建议总设计师更新进度：R2 交审，SOURCE G3 已通过，P1-0 先由 Claude 出计划，人员契约仅获方向授权；记录最终验证和 G3 结论后才能宣称工作包验收。用户暂缓 GitHub，不上传。未执行提交、推送、Git 配置、业务实现。
