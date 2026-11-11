# P1-C3 G3返工实际派发 v001

2026-11-11，总设计师followup原/root/p1c3_archive；沿用gpt-6.1-terra/high/fork_turns=none。此为同包明确缺陷修复，不改G1业务契约，原完整archive派发与禁止条件继续适用。

独立G3已确认REWORK，现场已由reviewer固定：archive_verify.py约145行仅catch OSError/ValueError/KeyError/BadZipFile；构造local+central压缩方法99的真实ZIP且自洽更新sidecar archive_sha256/bytes后，archive_run.py --verify返回1+traceback，而契约应拒绝码3。请在原白名单内做最小修复及有意义回归，不改其他共享源码/旧断言/契约。核已装Python3.11 zipfile实际异常与既定ZIP_DEFLATED格式，处理不支持方法与损坏压缩流/截断读取等预期不可信输入异常，安全映射ArtifactError到CLI3；避免捕获所有Exception掩盖程序错误。可先在成员读取前拒绝非本格式/加密，再对实际压缩流错误精确捕获。测试须使用真实ZIP+自洽sidecar，确保触发目标解析路径而非先哈希拒绝；真实CLI不得traceback。

只写archive_verify.py、必要归档相关原白名单测试与p1-c3-archive.md追加返工，若确需其他原白名单源码先说明。reviewer继续其他稳定文件，已暂停对这几个文件审阅；修完定向pytest与静态，明确停写、给SHA/测试数，root再联合fullcheck并交独立复测。不提交/推送，不触碰真实artifacts。

独立review实际协调：请把初次REWORK现场、文件SHA/行号、命令/退出码写handoff后先冻结对archive_verify/对应测试的审阅，继续其余稳定模块。root只放行归档作者对该明确缺陷做最小修复与测试，作者完成后再独立复测该输入及畸形流。不要同时基于变动中的verify代码下结论；最终G3须覆盖修后精确版本。
