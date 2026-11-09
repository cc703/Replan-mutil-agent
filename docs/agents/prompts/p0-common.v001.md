<!-- 来源: docs/source/p0_claude_plan_v001.original.md:198-283; 来源 SHA256: 82d49292f1342dce3c5348b5176d7cf029fe6fd10ddf61d884276ba8e61286f6; 摘录 SHA256: 83f634575b8065f3c2ec2b177d24c11c28fd0201b71cf09eddd0bc75677b74bf; 原文逐字，历史内容须服从现行 AGENTS 与用户裁决。 -->
# 公共前言（所有 P0 专项 Agent 必读）

## 项目与范围
项目：面向多约束场景的任务动态调度与重规划 Agent（本科毕业设计）。
当前阶段：P0 治理与协作基础。你只处理本工作包的文件。
绝对不做：P1–P8 的任何业务代码；不创建 src/ apps/ experiments/ 目录。

## 通用规则
1. 只能写入你的提示词里"允许写入"的文件；其他文件只读。
2. 不执行 git commit / push，不修改 git 配置与 remote；提交由总设计师负责。
3. 遇到"必须裁决"的问题（见下）立即停手，按"裁决请求单"格式提交，不要自行决定。
4. 文档使用中文；代码标识符、命令、路径、提交信息使用英文。
5. 不确定的事实（API、版本、许可证）先查官方来源再写，并在交接单里列出来源；无法核实就写"未核实"。
6. 不得编造文件内容来源；导入的设计文档必须逐字保留，只允许应用提示词中列出的修正。

## 必须裁决的问题（遇到即停）
论文范围或题目表述；算法设计与目标函数；评估协议与基线定义；数据契约；
引入 GPL/LGPL/AGPL/未声明许可证的依赖；外部服务、费用、密钥；
仓库可见性与许可证；偏离 design_v2 或 codex_spec；删除或重命名受保护文件；
改写历史或强制推送；涉及真实实验室数据或真人测试。

## 公共合同

C1 目录（P0 只创建 docs/ tools/ tests/governance/ artifacts/README.md）
   根目录允许（已跟踪/未忽略）：AGENTS.md README.md CHANGELOG.md LICENSE(可选)
   Makefile pyproject.toml uv.lock docker-compose.yml .gitignore .gitattributes
   .editorconfig .env.example .pre-commit-config.yaml .github
   docs src apps experiments data tests tools artifacts
   本地忽略项（不检查，.gitignore 必须包含）：
   .venv .env .mypy_cache .ruff_cache .pytest_cache __pycache__ node_modules
   .idea .vscode .DS_Store
   检查对象：git ls-files -co --exclude-standard

C2 命名规则
   R-N1 artifacts/** data/** experiments/configs/** docs/results/** src/**/*.py：
        小写 ASCII、数字、_ - .；Python 用 snake_case
   R-N2 docs/**（docs/results 除外）：允许中文与大写；ADR 用 NNNN-slug.md
   R-N3 根目录约定文件例外：AGENTS.md README.md CHANGELOG.md LICENSE Makefile
        Dockerfile .gitignore .gitattributes .editorconfig .env.example
        .pre-commit-config.yaml
   R-N4 框架例外：apps/backend/**（Java PascalCase、pom.xml、Flyway
        V<版本>__<描述>.sql，位置 apps/backend/src/main/resources/db/migration/）；
        apps/frontend/**（package.json、PascalCase.vue、vite.config.ts 等）
   R-N5 其他例外必须登记到 tools/layout_rules.toml 的 [exceptions]，写明理由，禁止 ** 全局例外

C3 产出物
   所有机器生成物只能在 artifacts/；artifacts/ 只有 README.md 入库。
   运行目录：artifacts/runs/<kind>/<name>/<run_id>/，必须有 manifest.json。
   run_id = YYYYMMDD-HHMMSS_<git短哈希>_<标签>
   manifest 必含：run_id kind name status started_at ended_at command git(commit,dirty)
   config_sha256 seeds versions solver_profile num_workers random_seed limit_kind
   源码目录不得出现 .log .csv .jsonl .tmp；.png .svg 仅 docs/results、
   apps/frontend/src/assets、apps/frontend/public 可出现。
   入库文件 ≤ 1MB；例外：uv.lock、package-lock.json。
   文件魔数必须与扩展名一致（png/pdf/svg）。

C4 依赖方向
   experiments → agent → scheduler_core；experiments → simulator → scheduler_core
   apps/* 仅通过 HTTP 调用 agent 服务
   scheduler_core 仅允许 标准库、ortools、numpy、pydantic；不得 import
   agent / simulator / experiments / 大模型 SDK
   simulator 不得 import agent
   b1_llm 位于 experiments/baselines/b1_llm.py

C5 求解器确定性配置档
   reproducible（默认）：num_workers=1、固定随机种子、确定性时间限制；用于黄金/属性测试与论文质量指标
   performance：多线程、墙钟限制、重复多次报告方差；用于规模与耗时实验
   具体参数名以已安装版本的官方文档为准（P2 核实）

C6 提交约定（供文档引用）
   Conventional Commits：type(scope): subject；scope 为工作包编号；
   一个工作包验收后一次提交；不强制推送、不改写历史。

## H 交接格式（交付时必须按此输出）
状态：DONE / BLOCKED / NEEDS-DECISION
变更文件：路径列表，每个标注 新增/修改，并写一句用途
验证：执行过的命令与结果摘要（复制真实输出，不要概括）
来源：引用的官方文档/外部资料链接与检索日期；未核实项单独列出
与合同的偏差：无 / 逐条说明
未决问题：无 / 列表
需裁决问题：无 / 按"裁决请求单"填写
下一步建议：一句话

## 裁决请求单格式
标题；背景（2-3 句）；选项 A/B(/C) 各含 优点、缺点、影响范围；
你的推荐与理由；不裁决的后果；需要裁决的截止点。
