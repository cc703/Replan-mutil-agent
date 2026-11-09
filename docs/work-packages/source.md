# SOURCE 工作包

- 阶段 P0；角色 source；实施会话 `/root/source_terra`，模型 `gpt-6.1-terra`、推理 high、fork_turns none。状态 IN-REVIEW，G1/G2/G3 PASS；G5 仅本地 checkpoint、远端暂缓。
- Claude 计划与全文：[continuation v001 第2、3节](continuation-claude-v001.md)。目标逐字入库并校验三份原文，勘误独立记录，不改规格。
- 允许写入：docs/source 下三份 original、manifest.json、MANIFEST.md、ERRATA.md、README.md；tools/verify_source.py、tests/governance/test_verify_source.py；.gitattributes 仅追加字节保护规则。其他只读。
- 输入：原文、全文和逐 200 行哈希、既有规格及 Claude 计划。当前采用整文件 Copy 加全文及逐批哈希核验；不需批次重生成。某文件不匹配则该文件阻塞。
- 验收：全文与批次哈希、字节数、行数一致，校验工具与治理测试通过，勘误摘录逐字核对，字节保护生效；具体细则见 Claude 提示词。风险：传输损坏或换行转换；不覆盖原有规格。
- 独立审查 `/root/review_terra` 在修复清单唯一性、批次覆盖与路径边界后给出 ACCEPT。交接与真实验证见 [SOURCE G3 记录](../agents/handoffs/source-g3.md)。共享工作树，互斥写入；专项不切分支、不提交推送。
