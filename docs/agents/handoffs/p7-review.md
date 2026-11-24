# P7 独立 G3 审查

审查者 `/root/p7_review`，实际配置 `gpt-6.2-sol / low / fork_turns=none`。依据 P7 工作包 G1、Claude Sonnet 5.5 Medium v001 §八、三份 G2 交接及实际代码。基线 `5a423d28943a6b2dde43ba02ed50441b426af407`。本记录只覆盖 P7。

## 初审结论 REWORK

1. **高｜PLAN_COMMIT 预览绕过当前世界验证。** 原 `Writes.java` PLAN_COMMIT 分支在校对基础版本和哈希后，直接返回存档的 diff 和 validation。真实复现：保存候选及有效 L2，注入仅与该候选冲突的停用事实。作业读取隐藏候选，执行拒绝为 422，重新请求同候选确认预览却返回 201 与 `validation.passed=true`。候选、提交及预览需要共用当前快照的判定。
2. **高｜活动版本差异泄露当前事实下不可用的计划。** 原 `Reads.java` 的 diff 分支只用归档世界验证两个版本。真实复现：提交 v2 后，停用 v2 某任务实际使用的设备时段，版本详情返回 `NEEDS_REPLAN` 且无计划或视图；同版本 diff 返回 200 与一条分配变化。需要对作为比较基线或目标的活动版本执行同一当前世界门禁，历史读取继续用存档证据。
3. **复验关注｜确认预览缓存。** 当前事实变更后同键重放仍属于一次展示，计划预览需再次判定安全。正式动作的幂等重放返回已发生的版本元数据。需覆盖提交与回滚两种预览，说明安全拒绝如何影响原合同的同键回包约定。

## 独立验证证据

测试连到实际 FastAPI、Spring、Vue 和 PostgreSQL 17.12 共享演示栈 `http://127.0.0.1:15403`，另建合成实验室。按 README 启动的栈由 root 维护。探针以独立客户端执行，请求和数据库观测来自真实组件。

- 原文完整性 `uv run --locked --python 3.11 python tools/verify_source.py` 全部 PASS。基线差异含新增未跟踪源码。核心、仿真器、P6 Agent、已核验原文及 ADR 路径无变更。检查未发现新增 skip、xfail、候选授权构造或第二求解器。未运行统一检查。
- 设置 `PYTHONPATH=src`、本机 PostgreSQL 环境和 `P7_PSQL` 后，执行 `uv run --locked --python 3.11 python tools/e2e_p7.py --url http://127.0.0.1:15403`。ArtifactStore 运行 `20261124-070945_5a423d2_http-db` 完成，记录 154 个请求。数据库读得 v1/v2 共两个版本、唯一 ACTIVE、作业 COMMITTED、事件 APPLIED、L2 CONSUMED、17 条审计，独立校验通过且 t1 移至 3–5 槽。实测 INFEASIBLE 未决结果阻塞，放弃后下一批包含原事实和并发提交的 8 条事件。
- 在 `apps/frontend` 设置 `P7_FRONTEND_URL=http://127.0.0.1:15403`，执行 `npx playwright test --output ../../artifacts/tmp/p7-review-playwright`。真实 Chromium 主线 `1 passed (10.4s)`。
- `uv run --locked --python 3.11 python artifacts/tmp/p7-review-probe.py http://127.0.0.1:15403`。复现两项缺陷，另验证已确认 L1 的秒级过期、载荷被改拒绝后原载荷仍可消费、不同事件键重用已消费确认被拒绝。初审输出为 `preview 201 None validation {'passed': True, 'violations': []}` 与 `diff 200 None changes 1`。
- 同样环境执行 `artifacts/tmp/p7-review-more.py`。实际极小 CP-SAT 预算返回 TIMEOUT，无核、松弛或候选，未决阻塞至丢弃。L1 试图走提交返回 409 级别不足，跨实验室 L1 拒绝。L2 回滚生成连续 v3、以 v2 为父、保留当前停用窗口、采用 v1 分配，同键重放返回 v3；无 L2 执行返回 428。HTTP/DB 主线另验不可行回滚。
- 队列事务中使用 lab 行锁、`FOR UPDATE OF l SKIP LOCKED`、RUNNING/QUEUED/未决/ACTIVE 部分唯一索引。G2 实际 PostgreSQL 的随机 schema 探针覆盖不同实验室可同时认领、回滚事务异常后可再消费和恢复。root 的独立实际中断证据覆盖 RUNNING/BATCHED → JVM 进程停止 → 新 JVM FAILED/WORKER_RESTARTED 且事实 RELEASED。其本地 relay 只延迟 replan 请求，求解输出由真实组件提供。
- 候选元数据由真实核心 CP-SAT 产生。TIMEOUT 与 INFEASIBLE 分开，后者才可诊断并标注最小性。NEGOTIABLE 诊断松弛标为假设、成本单位明确，前端无采纳入口。E8 的非法候选产出在 Python 定向测试中替身注入，判定依旧由真实独立校验器执行。本审查另从有效候选后追加真实冲突事实触发拒绝。
- 对话真实 P6 Pydantic 解析及语义检查，抽取使用固定替身。模型只产草案，Spring 消费 L1 后才持久化事实。回环、actor 自报、真实 DeepSeek 未验、会话不跨进程、无 TASK_OVERRUN 与仿真控制、单 Spring 进程和 Chromium 范围均有披露。
- 抽查锁与安装树。vis-timeline 8.5.0 固定为 Apache-2.0 OR MIT，依赖锁枚举九类许可，无缺失许可条目。设备分组、任务条目、阻塞背景、差异叠加与北京时间展示见 Vue 实现和真实主线。CP-SAT 轴与数学转换保留在 Python，Java 归档时间为 timestamptz。Maven 解析树与锁定 POM 对照，应用依赖无被排除的 jakarta.annotation-api 或 Logback。Python 新直接依赖和解析版本与 G2 登记相符。完整发行物的第三方 NOTICE/分发义务、多 Spring 实例、Docker Compose 实际执行均未在独立验证覆盖。

## 定向返工复验

2026-11-24，在新版真实集成栈 `http://127.0.0.1:15413` 对 Spring 返工复验。以 `PYTHONPATH=src` 分别执行 `uv run --locked --python 3.11 python artifacts/tmp/p7-review-probe.py http://127.0.0.1:15413 --fixed` 和 `uv run --locked --python 3.11 python artifacts/tmp/p7-review-more.py http://127.0.0.1:15413 --fixed`，两条命令退出 0。

- PLAN_COMMIT 在有效世界创建预览并同键重放均为 201。新增冲突事实后，新建及同键请求均返回 `422 VALIDATION_FAILED`，无预览；该旧选择也不出现在作业候选列表。执行返回同码。通过本机 `psql -d p7_demo` 查询该 L2，结果 `CONFIRMED|t`，第二列表示 `consumed_at IS NULL`。
- 活动 v2 受新确认事实冲突后，版本详情仍为 `NEEDS_REPLAN`；分别将 v2 用作 diff 的目标和基线，均为 `422 VALIDATION_FAILED`，无变化列表。归档版本读取和仅归档的比较返回 200。
- PLAN_ROLLBACK 有效预览的同键回复与首个 201 一致。新增使目标不可行的已确认事实后，新建与同键请求都返回 `422 ROLLBACK_INFEASIBLE`。独立复验另创建并重放了有效的正式回滚 v3。合同记录了两类 L2 预览重放在当前安全判定失败时的拒绝行为，正式写操作仍返回原结果。
- `psql` 核实实际数据库有 `job_queued`、`job_running`、`job_undecided`、`plan_active` 索引。PostgreSQL 17 SQL 锁行为与官方 [SELECT 锁定子句](https://www.postgresql.org/docs/17/sql-select.html#SQL-FOR-UPDATE-SHARE) 相符。
- Python 定向复验 `uv run --locked --python 3.11 pytest -q tests/service` 为 9 passed（Starlette TestClient 的 AnyIO 别名弃用提示）；含真实 CP-SAT 极小预算与可行/不可行分支、独立验证、OpenAPI 和样例同步、P6 接线。
- 审查另发现 Vue `confirmation.vue` 只渲染 `preview.payload`、事件回译及警告，跳过两类正式计划的差异和验证。回滚操作者在最终 L2 窗口只能看到目标与基线编号。该 G1 操作预览缺口由 Vue 原作者分段返工，结论待定向复验。

## 最终结论 ACCEPT

Spring 三处预览及差异门禁问题均通过真实 HTTP/PostgreSQL 定向复验。Vue 两类 L2 弹窗现展示独立校验和任务变化，提交另显示 f1/f2/f3；失败或缺少校验证据时禁用确认。

- 在 `apps/frontend` 独立执行 `npm run lint` 和 `npm run test -- tests/confirmation.test.ts`。类型检查退出 0，6 tests passed，覆盖 f1=0 仍显示、回滚使用 changes、失败与缺证据禁确认、L1 及幂等重试。
- 以新版前端与实际 Spring/FastAPI/PostgreSQL，设 `P7_FRONTEND_URL=http://127.0.0.1:15413` 后执行 `npx playwright test --output ../../artifacts/tmp/p7-review-playwright-final`，Chromium 1 passed (8.4s)。对候选提交的 L2 弹窗验证独立校验、f3 和重规划任务差异。
- 另用 `artifacts/tmp/p7-review-browser-lab.py` 在新版真实栈建立可回滚情形，执行 `node artifacts/tmp/p7-review-browser.cjs http://127.0.0.1:15413 7d52fae6-af00-457c-8288-f979862f190c`。真实 Chromium 在版本页查看 v1，打开回滚 L2，看到“独立校验通过”和“任务变化”，确认后出现 v3。无接口拦截或浏览器数据替身。

本次 G3 结束。无新增需用户裁决的业务项。root 负责最终统一检查、交付和 G5 同步。
