<!-- 来源: docs/work-packages/continuation-claude-v001.md:25-40; 来源 SHA256: 1f25a8e433493f28cea45a3555a5438ebf2eb25e0f8024d7646ca9011f32d312; 摘录 SHA256: 6b999a219a91c6a03915f1ec7e8130cd3f89d1dc05ca6c0c91e8121b26a40c02; 原文逐字，历史内容须服从现行 AGENTS 与用户裁决。 -->
# 公共前言增量 v002

运行配置：模型 GPT-6.1 Terra，推理 high（用户指定，由总设计师在派发界面设置）。
交接单必须写明实际使用的模型与推理档；无法确认则写"未能确认"，不得猜测。

新增规则
1. 不得静默升级规格：不产生 v1.2，不改写 docs/design_v2.md、docs/codex_spec.md 及 docs/source 下的原文。
   发现的错误或冲突一律记录到勘误或讨论文件，状态词只用 OPEN / DEFERRED-BY-USER / RESOLVED。
2. 用户已决定"B1 外移"与"求解器双 profile"两条建议暂不改；只做批注，状态为 DEFERRED-BY-USER，不得改动原契约。
3. 环境为 Windows：所有命令用 python 直接入口，不依赖 make。
4. GitHub 暂不上传：不登录、不 push、不配置远端凭据。Git 账号标识 cc703，作者标识 chm；
   文件中不得出现邮箱、真实姓名或任何密钥。
5. 不创建 src/ apps/ experiments/ 目录，不写任何 P1 及以后的业务代码，不冻结数据契约。
6. 不执行 git commit / push，不改 git 配置；提交由总设计师统一进行。
7. 现有治理测试（23 项）、ruff、mypy 必须保持通过；任何触及它们的改动先报告。
8. 遇到必须裁决的问题立即停手，按裁决请求单格式上报。
