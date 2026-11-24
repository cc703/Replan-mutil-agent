# Claude P7 规划 v001

来源：2026-11-24，用户在 Claude 原会话发送交接请求，root 从右侧 Claude（页面显示 Sonnet 5.5 Medium）读取最新完整回复。以下是页面渲染内容转录，表格排版还原，代码块保留原换行。此文件是 Claude 提议的历史记录，G1 裁决另见 P7 卡。

## P7 计划：前后端、持久化与本地端到端演示

适用范围：P6 已验收，基线与验收标签目标为 5a423d28943a6b2dde43ba02ed50441b426af407。本包是一个工作包，一次独立审查，P8 不在本包。

说明：以下为提议，我没有读过本机源码。依据是设计 v2 第 8–10 节（959–1111）与开发规格 P7 行（559）、D3（579）、D6（582）。凡涉及 P1–P6 内部 API 的地方，都写成"先读源码再接线"，不凭记忆指定函数名。

---

### 一、目标与范围

#### 1.1 主线

注入事件 → 异步重规划 → 展示候选与差异 → 用户选择并确认 → 提交 → 状态更新。覆盖旧版本、确认缺失、重复请求、同实验室并发。

#### 1.2 保留的原设计界面与入口

| 页面或入口 | P7 保留的范围 |
| --- | --- |
| 计划视图 | 完整：vis-timeline，设备为分组行，任务为条目，CLOSED、MAINT、FAULT、RUNNING 窗口为背景条目；颜色区分变化与延期 |
| 重规划工作台 | 完整：事件注入表单与预览、事件列表、作业状态、候选对比表、差异叠加视图、解释、选择、L2 确认与提交；INFEASIBLE 与 TIMEOUT 的专门展示 |
| 对话面板 | 完整接线：P6 的澄清与确认卡片，经同一 L1、L2 门禁 |
| 版本与审计 | 版本列表（含父版本）、版本差异、回滚（L2）、决策日志 |
| 资源管理、任务管理 | 只读表格加整份实例 JSON 导入（创建实验室） |
| 仿真控制台入口 | 仅保留入口页，复用工作台的手动事件注入组件；明确写"仿真运行控制未实现" |

#### 1.3 本包不做（须如实披露，不得伪造界面）

资源与任务的增删改、CSV 导入、SSE 流式对话、雷达图（用表格代替）、仿真启动暂停与倍速及指标曲线、真实登录与角色、TASK_OVERRUN 事件注入（P7 不托管执行状态，注入时返回 UNSUPPORTED_EVENT）、完整容器化部署（只提供 PostgreSQL 的 compose）、真实 DeepSeek 在线验证、正式 D7 评测。

---

### 二、架构与接口边界

```text
浏览器(Vue) ──HTTP /api/v1──▶ Spring Boot（业务薄层，PostgreSQL）──HTTP /internal/v1──▶ FastAPI（调度与 Agent）
                                      │                                                         │
                                  PostgreSQL                                        scheduler_core / agent / simulator
```

浏览器只访问 Spring，不直连 FastAPI。FastAPI 的 /internal/* 不对外暴露。
Spring 只做：持久化、计划版本与乐观锁、事件记录与审计、确认协议、异步作业队列、网关转发。不放任何算法，不做时间槽换算与校验。
FastAPI 负责：初始调度、重规划候选（含 P5 诊断与松弛）、独立校验、差异、视图 DTO（含 ISO 时间）、Agent 回合、哈希（规范字节）。
Spring 不重新序列化计划：原样存 FastAPI 返回的 JSON，哈希一律取自 FastAPI，防止 Java 与 Python 规范化不一致。
OpenAPI 先行：FastAPI 的 OpenAPI 导出到 apps/contracts/scheduler-service.openapi.json，有"文件是最新的"测试；真实响应样例放 apps/contracts/examples/，由 Python 测试生成并校验，Spring 和 Vue 的测试读取它们。

---

### 三、契约 CB-P7

#### 3.1 公共约定

```text
路径前缀：对外 /api/v1，对内 /internal/v1。JSON UTF-8；未知字段一律拒绝（Pydantic extra=forbid；Jackson FAIL_ON_UNKNOWN_PROPERTIES）。
请求体上限 8 MB；超过 → 413 PAYLOAD_TOO_LARGE。时间：API 中为带偏移的 ISO-8601 字符串；换算只在 FastAPI（经 inst.axis，严格对齐）。
追踪：请求头 X-Trace-Id（缺省则生成），Spring 与 FastAPI 原样透传并写入日志与错误体。
幂等：会修改状态的 POST（events、commit、rollback、discard、confirm 动作）要求头 Idempotency-Key（≤128 字符）。
  同键同请求体 → 返回首次响应，并加头 Idempotent-Replay: true；同键不同请求体 → 409 IDEMPOTENCY_KEY_REUSED。
  事件另有 client_event_id（每实验室唯一）：重复且内容相同 → 返回已有事件；内容不同 → 409 DUPLICATE_EVENT_CONFLICT。
错误体：{"error":{"code":"…","message":"…","details":{…},"trace_id":"…"}}。
```

#### 3.2 错误码（Spring 对外；FastAPI 使用同一信封，码前缀相同的子集）

```text
400 VALIDATION_ERROR（请求结构错）  TIME_NOT_ALIGNED  UNKNOWN_ENTITY（设备或任务不存在）
    UNSUPPORTED_EVENT  UNSUPPORTED_CONSTRAINT_TYPE  INVALID_EVENT（details.index 指明）  INVALID_INSTANCE
404 NOT_FOUND
409 STALE_BASE_VERSION  IDEMPOTENCY_KEY_REUSED  DUPLICATE_EVENT_CONFLICT  JOB_NOT_COMMITTABLE
    CANDIDATE_NOT_FOUND  CONFIRMATION_NOT_CONFIRMED  CONFIRMATION_CONSUMED  CONFIRMATION_EXPIRED
    CONFIRMATION_MISMATCH（载荷哈希、实验室、基础版本不符）  CONFIRMATION_LEVEL_INSUFFICIENT  LAB_BUSY（需要空闲的操作遇到未决作业）
413 PAYLOAD_TOO_LARGE
422 VALIDATION_FAILED（独立校验器拒绝，details.violations 含 code、reason）  ROLLBACK_INFEASIBLE  PLAN_INTEGRITY_ERROR
428 CONFIRMATION_REQUIRED（缺确认）
502 SCHEDULER_UNAVAILABLE  504 SCHEDULER_TIMEOUT（网关超时，不等于求解 UNKNOWN）
500 INTERNAL_ERROR
FastAPI 额外：LLM_UNAVAILABLE、LLM_OUTPUT_INVALID（Agent 端点）。
```

#### 3.3 Spring 对外 API

```text
POST /labs  {name, instance}   → 201 {lab_id, name, instance_sha256, summary{tasks,devices,persons}, active_version_no:0}
            先经 FastAPI instances/check；INVALID_INSTANCE 时 422 之外不落库。
GET  /labs  |  GET /labs/{labId} → {…, active_version_no, running_job_id|null, undecided_job_id|null, pending_event_count}
POST /labs/{labId}/plans/initial  {params?{time_limit_s,num_workers,seed,objective_weights}} → 202 {job_id, status:"QUEUED"}
GET  /labs/{labId}/plans  |  GET /labs/{labId}/plans/{n}  → {version_no, parent_version_no, status, created_at, plan, plan_sha256, view}
GET  /labs/{labId}/plans/{n}/instance   GET /labs/{labId}/plans/{n}/diff?base={m} → {changes:[…]}
POST /labs/{labId}/confirmations {action, level, payload, actor, ttl_s?}
     → 201 {confirmation_id, action, level, payload_hash, preview, expires_at, status:"PENDING"}
POST /labs/{labId}/confirmations/{id}/confirm {actor, payload_hash} → 200 {status:"CONFIRMED"}   |  …/reject
POST /labs/{labId}/events {client_event_id, event, confirmation_id, actor} → 202 {event_id, status:"RECEIVED"}
GET  /labs/{labId}/events?status=
GET  /labs/{labId}/jobs  |  GET /labs/{labId}/jobs/{jobId} →
     {job_id, kind, status, result_status|null, base_version_no, event_ids, created_at, started_at, finished_at,
      error{code,message}|null, candidates[], conflict|null, relaxations[], solver{…}}
POST /labs/{labId}/jobs/{jobId}/discard {reason, actor} → 200（释放事件）
POST /labs/{labId}/plans/commit   {job_id, candidate_id, base_version_no, confirmation_id, actor} → 201 {version_no, status:"ACTIVE", …}
POST /labs/{labId}/plans/rollback {target_version_no, base_version_no, confirmation_id, actor} → 201 {version_no, …}
GET  /labs/{labId}/decisions
POST /labs/{labId}/agent/turn {session_id?, text, actor} → 200 {session_id, assistant_message, clarifications[], pending_items[{item_id, ir, back_translation, ambiguities}]}
GET  /health
API 事件（含时间的字段均为 ISO，时长为分钟，需为槽的整数倍）：
  DEVICE_OUTAGE {type, device_id, start, end}
  URGENT_INSERT {type, tasks:[{id, experiment_id, type, duration_minutes, release?, deadline?, deadline_level?, weight?,
                 compatible_devices[], demand?, required_skills?[], requires_person?}], precedences?:[{pred, succ, lag_min_minutes?, lag_max_minutes?}]}
候选对象：{candidate_id, label, level, weights, f1, f2, f3, validation{passed, violations[]}, diff[], view, explanation|null, plan_sha256}
relaxations 元素：{description, cost, cost_unit:"任务权重×截止期延后槽数", relaxed_groups, deltas, verified, hypothetical:true}
```

#### 3.4 确认协议（L1 与 L2）

```text
动作与级别固定：EVENT_INJECT、CONSTRAINT_CHANGE 为 L1；PLAN_COMMIT、PLAN_ROLLBACK 为 L2。级别或动作不符 → CONFIRMATION_LEVEL_INSUFFICIENT 或 CONFIRMATION_MISMATCH。
载荷：EVENT_INJECT = 事件对象；PLAN_COMMIT = {job_id, candidate_id, base_version_no, plan_sha256}；
      PLAN_ROLLBACK = {target_version_no, base_version_no}；CONSTRAINT_CHANGE = {ir_item_id}（仅限 P6 已实现且已验证的类型，其余 UNSUPPORTED_CONSTRAINT_TYPE）。
payload_hash = sha256(规范 JSON：键排序、UTF-8、无多余空白)；创建时生成预览（EVENT_INJECT 经 FastAPI events/preview 得回译文本、归一化事件与警告；
  PLAN_COMMIT 含候选指标、差异、校验结果、基础版本；PLAN_ROLLBACK 含目标版本差异与预校验结果）。
状态：PENDING → CONFIRMED → CONSUMED；或 REJECTED、EXPIRED（默认 15 分钟，配置项）。
动作端点要求 confirmation_id：缺 → 428 CONFIRMATION_REQUIRED；PENDING → CONFIRMATION_NOT_CONFIRMED；
  已使用 → CONFIRMATION_CONSUMED；过期 → CONFIRMATION_EXPIRED；
  实际动作载荷的哈希、实验室、基础版本与确认记录不符 → CONFIRMATION_MISMATCH。
消费必须与动作在同一事务内，用 UPDATE … WHERE status='CONFIRMED' 抢占；失败即整个动作回滚。
本包无登录：actor 为自报字符串，只写入审计；L1、L2 是协议级二次确认，不是身份认证。
```

#### 3.5 作业队列与批次规则

```text
事件状态：RECEIVED → BATCHED(job) → APPLIED；作业被放弃、失败、过期时 BATCHED → RELEASED（视同 RECEIVED）；校验或归一化失败 → REJECTED。
作业种类：INITIAL、REPLAN。状态：QUEUED → RUNNING → SUCCEEDED（result_status ∈ OK、INFEASIBLE、TIMEOUT）｜FAILED；
  SUCCEEDED 之后：COMMITTED｜DISCARDED｜STALE。
入队：事件落库后，若该实验室没有 QUEUED 作业，则新建 QUEUED 作业，not_before = now + merge_window_ms（默认 500，配置项）。
认领条件（事务内）：该实验室没有 RUNNING 作业，且没有"未决"作业（状态为 SUCCEEDED、尚未 COMMITTED、DISCARDED、STALE）。
  认领时才组批：该实验室全部 RECEIVED 与 RELEASED 事件按 (created_at, id) 升序，至多 50 个，置 BATCHED。
  基础版本 = 认领时的 active_version_no。运行中到达的新事件保持 RECEIVED，进入下一批。
硬保证：数据库部分唯一索引 CREATE UNIQUE INDEX ON job(lab_id) WHERE status='RUNNING'；认领用 SELECT … FOR UPDATE SKIP LOCKED，并锁定实验室行。
  不同实验室可并行运行。
版本变化（提交、回滚）时：该实验室未决作业置 STALE，其 BATCHED 事件置 RELEASED。
启动恢复：RUNNING 作业置 FAILED（error=WORKER_RESTARTED），事件 RELEASED。
FastAPI 报 INVALID_EVENT（details.index）：对应事件置 REJECTED，其余事件重新排队；其他失败置 FAILED 并释放事件。
放弃（discard）：作业置 DISCARDED，BATCHED 事件置 RELEASED。INFEASIBLE 与 TIMEOUT 的作业也需放弃才能释放事件（未决规则的有意后果）。
```

#### 3.6 版本、乐观锁与回滚

```text
lab.active_version_no 初始为 0；提交的 base_version_no 必须等于它，初始计划提交用 0。
提交事务（先做无锁的预检与外部校验，再进入事务）：
  预检：作业为 SUCCEEDED 且 result_status=OK；候选属于该作业；作业的基础版本等于当前版本；确认有效；
        调用 FastAPI validate（基于作业保存的 instance_post、候选计划、基础计划，传 expected_plan_sha256），必须通过，否则 422 VALIDATION_FAILED，不入库。
  事务：SELECT … FOR UPDATE 锁实验室行 → 复核版本（不符 → 409 STALE_BASE_VERSION，作业置 STALE）→ 消费确认 →
        插入 plan_version（保存 plan、instance_post、view、哈希）→ 前一版本置 SUPERSEDED → 更新 lab.active_version_no →
        作业置 COMMITTED，事件置 APPLIED → 写 decision_log → 保存幂等响应。
回滚（U3，待确认）：新建版本 n+1，内容为目标版本的计划，实例为**当前活动版本的实例**；用 FastAPI validate（基础为当前计划）校验，
  不通过 → 422 ROLLBACK_INFEASIBLE，不入库；不恢复旧实例。回滚同样要 L2 确认与幂等。
```

#### 3.7 FastAPI 内部 API

```text
GET  /internal/v1/health → {status, versions{python, ortools}}
POST /internal/v1/instances/check {instance} → {ok, instance_sha256, summary}
POST /internal/v1/initial {instance, params?} → {result_status, plan?, plan_sha256?, view?, validation, solver{…}}
POST /internal/v1/events/preview {instance, base_plan, event} → {ok, back_translation, event_normalized, warnings}
POST /internal/v1/replan {instance, base_plan, events[API 事件], context?, params?, max_candidates, explain, budget_s?} →
     {result_status: OK|INFEASIBLE|TIMEOUT, instance_post, instance_post_sha256, candidates[…], impact{frozen,affected,unaffected},
      conflict{group_ids, descriptions, minimal}|null, relaxations[…], solver{ortools_version, wall_seconds, budget_s}, warnings[]}
POST /internal/v1/validate {instance, plan, base_plan?, free?, context?, expected_plan_sha256?} → {passed, violations[], plan_sha256_ok}
POST /internal/v1/diff {instance, base_plan, plan} → {changes[]}
POST /internal/v1/view {instance, plan, base_plan?} → {devices[], assignments[含 ISO 时间与槽], blocked[]}
POST /internal/v1/agent/turn（及 P6 的确认与选择入口，先读 P6 后薄封装，语义保持原样）
实现要点：events 的应用使用 P4 现有的事件应用逻辑，得到 instance_post 并随结果返回（先读 P4 找到函数）；
  候选展示前必经 validate；通不过的候选不返回；budget_s 默认取 ReplanParams 默认，上限 120；
  result_status 的映射：P5 的 OK、INFEASIBLE、TIMEOUT 原样，TIMEOUT 不诊断、不声称不可行。
```

#### 3.8 PostgreSQL（Flyway V001，路径 apps/backend/src/main/resources/db/migration/）

```text
lab(id uuid pk, name, instance jsonb, instance_sha256, active_version_no int default 0, created_at)
plan_version(lab_id, version_no, parent_version_no, status ACTIVE|SUPERSEDED, plan jsonb, plan_sha256, instance jsonb, instance_sha256,
             view jsonb, source ENUM(INITIAL,REPLAN,ROLLBACK), job_id null, created_by, created_at, pk(lab_id, version_no))
event(id uuid pk, lab_id, client_event_id, payload jsonb, status, job_id null, confirmation_id, created_by, created_at, unique(lab_id, client_event_id))
job(id uuid pk, lab_id, kind, status, result_status null, base_version_no, not_before, started_at, finished_at, error_code, error_message,
    result jsonb null, created_at, 部分唯一索引：lab_id WHERE status='RUNNING')
candidate(id uuid pk, job_id, candidate_key, label, level, plan jsonb, plan_sha256, metrics jsonb, diff jsonb, validation jsonb, view jsonb, explanation jsonb null)
confirmation(id uuid pk, lab_id, action, level, payload jsonb, payload_hash, preview jsonb, status, requested_by, confirmed_by null, expires_at, consumed_at null)
decision_log(id bigserial pk, lab_id, actor, action, subject_type, subject_id, details jsonb, at)
idempotency(lab_id, key, request_hash, status_code, response jsonb, created_at, pk(lab_id, key))
ir_item(id uuid pk, lab_id, session_id, ir jsonb, back_translation, status DRAFT|CONFIRMED|REJECTED, event_id null, created_at)
agent_session(id uuid pk, lab_id, summary jsonb, updated_at)
Spring 数据访问用 Spring JDBC（JdbcClient 或 JdbcTemplate）加明确 SQL，jsonb 用参数绑定；不使用 ORM（偏离 v2 的"MyBatis-Plus 或 JPA"，须记 ADR）。
```

#### 3.9 业务语义（不得改动）

```text
求解器仍是 CP-SAT；本批紧急任务目标 f3 = Σ end_i（无紧急为 0）；所有截止期在无真实授权时严格。
松弛仅针对 NEGOTIABLE 截止期，代价 = Task.weight × 截止期延后槽数；松弛方案一律 hypothetical=true，
  界面标"假设提案，未授权，不可采纳"，后端没有采纳端点；任何代码不得创建或改绑 DeadlineAuthorization（grep 与 AST 测试断言）。
UNKNOWN（TIMEOUT）：不诊断，不声称不可行，界面提示"预算内未得出结论"；
INFEASIBLE：展示冲突核；conflict.minimal=false 时必须显示"已证明冲突，未证明不可约"。
正式展示与提交的计划都必须经独立校验器；展示用候选来自 FastAPI 且 validation.passed=true；提交前 Spring 再调 validate。
```

#### 3.10 LLM 与替身的验证边界

```text
自动化验收使用确定性替身 LLM（脚本化输出，经环境变量 P7_LLM=fake 启用），验证范围：接线、Pydantic 与语义校验、L1 与 L2 门禁、澄清与确认的回合流转。
不验证：真实 DeepSeek 在线行为、真实模型的抽取质量、跨进程会话恢复（FastAPI 会话状态不保证重启后存在）。
调度与校验使用真实 OR-Tools 与独立校验器，不得替身；为覆盖"校验失败"路径而做的调度器替身只出现在单元测试，且在交接单标明。
真实 DeepSeek 的手工冒烟可选，需密钥与网络，结果只能如实标注"手工、未纳入验收"。
```

---

### 四、写入权限

| 角色 | 路径（精确） |
| --- | --- |
| 实施（FastAPI） | src/service/**（含 app.py、settings.py、errors.py、schemas_*.py、routers/*.py、deps.py、hashing.py、openapi_export.py、__main__.py）；tests/service/**；apps/contracts/scheduler-service.openapi.json；apps/contracts/examples/*.json；apps/contracts/backend-api.md（第 3.1–3.6 节的可归档副本） |
| 实施（Spring） | apps/backend/pom.xml、mvnw、mvnw.cmd、.mvn/wrapper/**、apps/backend/src/main/java/io/replan/backend/**、src/main/resources/application.yml、db/migration/V001__init.sql（后续迁移只许 V002__* 起新增）、src/test/java/**、src/test/resources/** |
| 实施（Vue） | apps/frontend/package.json、package-lock.json、index.html、vite.config.ts、tsconfig*.json、playwright.config.ts、src/**、e2e/**、public/** |
| 实施（根部与工具） | docker-compose.yml、.env.example、.gitignore（仅追加 apps/backend/target/、apps/frontend/node_modules/、apps/frontend/dist/、apps/frontend/test-results/ 等）、pyproject.toml 与 uv.lock（仅 fastapi、uvicorn、httpx 等经核实的依赖）、tools/p7_stack.py、tools/e2e_p7.py、README.md（本地演示一节）、docs/engineering/dependency-register.md、docs/work-packages/p7.md、docs/agents/handoffs/p7.md |
| 条件限定 | tools/check_import_boundaries.py（仅为新增 service 包与 apps/* 的 HTTP 边界做最小放行并加治理测试）；tools/layout_rules.toml（仅当确认拒绝 .mvn、mvnw*、vite 等必要文件时，登记最小例外并写理由） |
| 审查只写 | docs/agents/handoffs/p7-review.md |
| root 单写 | 进度、registry、RESUME、CHANGELOG、提示词归档、最后一次统一检查与 P7 端到端验收、Git（普通同步与验收标签） |

禁止改：scheduler_core、simulator、P6 agent 的既有行为与断言（只允许新增调用方）、validator 规则、docs/source、ADR 状态、依赖版本的既有固定项；不引入 Kaiwu、QUBO、第二求解器；不创建或改绑 DeadlineAuthorization。

---

### 五、依赖与环境前置（实施 Agent 第一步，核实后才写代码）

- Python：fastapi、uvicorn、httpx（测试与 E2E）。
- Java：JDK（Spring Boot 3 要求的最低版本）、Spring Boot 3 的 web、jdbc、validation、actuator；Flyway（含 PostgreSQL 支持模块）、PostgreSQL JDBC 驱动；测试用 JUnit（随 Boot）、Awaitility、MockWebServer；Maven Wrapper。
- Node：Node LTS、Vue 3、Vue Router、TypeScript、Vite、Element Plus、vis-timeline 与其 vis-data 对等依赖、Vitest、Vue Test Utils、Playwright（Chromium）。
- Docker 镜像：PostgreSQL，固定主版本。
- 每一项都要从官方来源核实版本、官方 API 签名、许可证、Windows 与对应运行时的兼容性；固定版本，提交锁文件，登记依赖表（含传递依赖的许可证摘要）。出现 GPL、LGPL、AGPL、EPL、许可证不明者，标 NEEDS-DECISION，不得写入假设。vis-timeline 的版本与许可在 D3 中已要求本包核实。
- 环境预检：JDK、Node、Docker（或本机 PostgreSQL）、Playwright 浏览器是否可用。缺失则状态 NEEDS-ENV，写明具体缺项和安装命令，并停止依赖该项的阶段，不得用替身顶替真实 PostgreSQL。

---

### 六、验收主线与矩阵

| 编号 | 场景 | 必须证明 |
| --- | --- | --- |
| E1 | 主线：导入实例 → 初始作业 → 提交 v1 → 注入停用 → 重规划 → 候选与差异 → 选择 → L2 → 提交 v2 → 状态更新 | 候选均 validation.passed；提交的计划由 E2E 脚本用 P1 校验器独立重验通过；plan_version、event=APPLIED、job=COMMITTED、decision_log、confirmation=CONSUMED 与库中一致；UI 的 Playwright 主线通过 |
| E2 | 旧版本 | v1→v2 提交后，用基于 v1 的另一候选提交 → 409 STALE_BASE_VERSION，库无新版本，作业 STALE，事件 RELEASED |
| E3 | 确认缺失 | 无确认 → 428；PENDING 确认 → 409；重复使用 → 409；L1 确认用于提交 → 409；载荷被改 → 409；过期确认 → 409。事件注入同样适用 |
| E4 | 重复请求 | 相同 client_event_id、相同 Idempotency-Key 的重复 commit 与 confirm 均不产生第二条记录或第二个版本；同键不同体 → 409 |
| E5 | 同实验室并发 | 并发注入至少 8 个事件并同时触发认领：任意时刻库中该实验室 RUNNING 作业数 ≤1（采样查询并验证唯一索引存在）；运行中到达的事件进入下一批；两个实验室可同时 RUNNING；版本号连续无重复 |
| E6 | 结果语义 | INFEASIBLE：有冲突核、松弛项均 hypothetical=true、无可提交候选、提交 → 409 JOB_NOT_COMMITTABLE；TIMEOUT：无核、无"不可行"文案，界面显示"预算内未得出结论"；minimal=false 时显示未证明不可约 |
| E7 | 回滚 | 能通过校验时创建新版本；不能时 422 ROLLBACK_INFEASIBLE 且库不变；均需 L2 与幂等 |
| E8 | 校验门禁 | 用调度器替身返回不合法候选：不显示、不可提交；validate 替身拒绝 → 422 VALIDATION_FAILED。（替身，仅单元与集成层） |
| E9 | 对话 | 替身 LLM：回合 → 澄清 → 卡片 → L1 确认 → 事件入队；越过 L1 失败 |
| E10 | 重启与追踪 | 在作业 RUNNING 时重启 Spring：作业 FAILED（WORKER_RESTARTED），事件 RELEASED；X-Trace-Id 从浏览器到 FastAPI 日志连贯 |

E2E 产物：tools/e2e_p7.py 启动栈、运行 E1–E10 中可由脚本驱动的部分、通过 ArtifactStore 写运行记录到 artifacts/runs/experiment/p7_local_demo/<run_id>/（调用时间线、库状态摘要、校验结果），不入库。UI 主线由 apps/frontend/e2e/ 的 Playwright 测试覆盖。

检查命令（实施 Agent 自检，root 最后统一运行一次）：

```text
uv run --python 3.11 --group dev python tools/check.py
uv run --python 3.11 --group dev python -m pytest tests/service -q -p no:cacheprovider
apps/backend/mvnw -q verify            （需要 P7_TEST_DB_URL 指向 compose 的 PostgreSQL 测试库）
cd apps/frontend && npm ci && npm run lint && npm run test && npm run build
uv run --python 3.11 --group dev python tools/p7_stack.py up ；python tools/e2e_p7.py ；python tools/p7_stack.py down
uv run --python 3.11 --group dev python tools/check_repo_layout.py ；python tools/verify_source.py ；git diff --check
```

---

### 七、实施提示词

```text
[附公共前言、增量 v002、契约 CB-P7（本文件第三节）] 运行配置：gpt-6.2-sol，推理 low，fork_turns=none。你没有先前上下文，下面是全部背景。按顺序一步一步做，不要跳步，不要自行扩大范围。

# 角色与目标
P7 实施 Agent。交付：FastAPI 服务（调度与 Agent 接口）、Spring Boot 业务薄层（真实 PostgreSQL）、Vue 前端，以及可在本地真实运行的端到端演示。
主线：注入事件 → 异步重规划 → 展示候选与差异 → 用户选择并确认 → 提交 → 状态更新。
你不提交、不推送、不改 Git。代码简单完整，职责分文件，函数约 20–60 行、文件约 150–300 行（仅参考）。完整类型与注释。

# 文件权限
只能写第四节"实施"各行列出的路径；条件限定的两项只在满足条件时做最小修改，并在交接单说明。
禁止改：scheduler_core、simulator、P6 agent 的既有行为与断言、validator 规则、docs/source、ADR 状态、既有固定依赖版本。
禁止：Kaiwu、QUBO、第二求解器；创建或改绑 DeadlineAuthorization；把 hypothetical 松弛方案做成可采纳；
用替身顶替真实 PostgreSQL、真实 OR-Tools 或独立校验器（E8 的单元层替身除外）；新增 skip 或 xfail；弱化旧断言；提交 node_modules、target、dist、密钥。

# 阶段 0：预检与核实（必须先完成，结果写进交接单）
0.1 运行 uv run python tools/verify_source.py。
0.2 读 P1–P6 的真实代码，列出并记录：Instance、Plan、Event、ValidationContext 的 JSON 形态；P4 的 replan 与"应用事件得到 instance_post"的函数；
    P5 的 replan_candidates、plan_diff；P6 的 agent 入口（澄清、确认、选择、解释）与其 LLM 接口和测试替身；规范计划字节的现有函数；
    simulator 与 service 之间的边界。凭源码确认，不凭记忆。
0.3 环境预检：JDK、Maven Wrapper、Node、Docker 或本机 PostgreSQL、Playwright 浏览器。缺项 → NEEDS-ENV，写明缺项与安装命令，停止依赖该项的阶段。
0.4 依赖核实（第五节）：官方版本、API、许可证、兼容性；固定版本、锁定、登记。不明许可证 → NEEDS-DECISION。

# 阶段 1：FastAPI 服务（src/service）
1.1 实现第 3.7 节全部端点与第 3.1、3.2 节的信封、追踪、幂等相关的服务端行为（FastAPI 侧只需追踪头与错误信封）。
1.2 events/preview：时间严格对齐；设备、任务引用检查；紧急任务结构检查；返回中文回译文本与归一化事件；错误用 TIME_NOT_ALIGNED、UNKNOWN_ENTITY、INVALID_EVENT。
1.3 replan：使用 P4 与 P5 的现有函数；候选在返回前必经 validate，不通过者丢弃并写 warnings；返回 instance_post 与其哈希；
    TIMEOUT 不做诊断；INFEASIBLE 填 conflict（含 minimal）与 relaxations（统一加 hypothetical=true、cost_unit）。
1.4 validate、diff、view、initial、instances/check；canonical 哈希只在此处计算。
1.5 agent：薄封装 P6，LLM 输出的所有字段经 P6 的 Pydantic 与语义校验；P7_LLM=fake 时使用 P6 已有的确定性替身（没有则按 P6 的接口写最小脚本化替身，放 tests）。
1.6 导出 OpenAPI 到 apps/contracts/scheduler-service.openapi.json；用测试生成并校验 apps/contracts/examples/*.json（至少：初始结果、replan OK、INFEASIBLE、TIMEOUT、错误信封、校验失败）。
1.7 tests/service：每个端点的成功与错误路径；错误码对应；OpenAPI 文件最新；无 DeadlineAuthorization 创建（grep 与 AST）；
    不修改入参；TIMEOUT 不含冲突核；候选全部 validation.passed；追踪头回显。
    定向检查：pytest tests/service；ruff；mypy；布局。

# 阶段 2：Spring 持久化、队列与确认（apps/backend）
2.1 建 Maven 工程（包 io.replan.backend），Flyway V001 按第 3.8 节建表，包含部分唯一索引与各唯一约束；application.yml 外置配置
    （数据库 URL、FastAPI 地址、超时、merge_window_ms、确认有效期、批大小），密钥仅走环境变量。
2.2 对外 API 全部按第 3.3 节；错误信封与错误码按第 3.1、3.2 节；Jackson 拒绝未知字段；请求体上限；X-Trace-Id 透传并写日志。
2.3 确认协议按第 3.4 节：创建、确认、拒绝、消费；消费与动作同一事务。
2.4 事件与作业队列按第 3.5 节：入队、认领（锁定实验室行加 SKIP LOCKED）、组批、运行（调用 FastAPI，设置超时）、结果落库、启动恢复、
    INVALID_EVENT 处理、discard。
2.5 提交与回滚按第 3.6 节：先预检与 validate，再事务；STALE 处理与未决作业置 STALE；回滚语义按 U3 的推荐。
2.6 幂等表与 client_event_id；decision_log 写入所有决定类动作。
2.7 测试（真实 PostgreSQL，环境变量 P7_TEST_DB_URL；每个测试类用独立 schema 或 Flyway clean 后重建）：
    迁移与索引存在；认领的并发测试（多线程同时认领同一实验室，任意时刻 RUNNING ≤1，断言唯一索引拒绝第二个）；两个实验室并行；
    组批与"运行中事件进入下一批"；未决作业阻塞后续认领与 discard 释放；STALE 与事件释放；启动恢复；
    确认协议的全部错误路径（428、未确认、已消费、过期、载荷不符、级别不符）；消费与动作同事务（注入失败后确认仍为 CONFIRMED）；
    提交的成功与 STALE、校验失败不入库、幂等重放、同键不同体；回滚成功与 ROLLBACK_INFEASIBLE；
    FastAPI 用 MockWebServer 按 apps/contracts/examples 的真实样例响应（声明：此层为替身，验证边界是 Spring 对样例形态的处理）。
    定向检查：apps/backend/mvnw -q verify。

# 阶段 3：Vue 前端（apps/frontend）
3.1 页面与路由（中文界面）：/plan、/workbench、/chat、/versions、/resources、/tasks、/import、/sim（仅入口页，写明"仿真运行控制未实现"）。
3.2 计划视图：vis-timeline（核实后的版本与 API）：设备为分组，任务为条目，窗口为背景条目；颜色区分变化与延期；使用后端返回的 view，不在前端做时间槽换算。
3.3 工作台：事件表单（DEVICE_OUTAGE、URGENT_INSERT）→ 预览与 L1 确认 → 提交事件 → 事件与作业状态（轮询）→ 候选对比表（含 f1、f2、f3 的中文标注，
    f3 为"紧急任务完成时间总和"）→ 差异叠加视图（旧计划灰色，新计划彩色）与差异列表 → 解释 → 选择 → "将发生什么"预览 → L2 确认 → 提交 → 状态更新。
    INFEASIBLE：展示冲突核；minimal=false 时写"已证明冲突，未证明不可约"；松弛项标"假设提案，未授权，不可采纳"，页面上没有采纳按钮。
    TIMEOUT：写"预算内未得出结论，不代表不可行"，不展示冲突核。STALE、428 等错误码显示对应中文提示与下一步。
3.4 对话面板：回合、澄清问题、确认卡片（回译与可编辑字段）；确认走 L1；低置信度字段高亮。
3.5 版本与审计：版本列表、差异、回滚（L2）、决策日志。资源与任务页：只读表格；导入页：粘贴或上传实例 JSON 创建实验室。
3.6 API 客户端按 backend-api.md 与 examples 编写；所有写请求带 Idempotency-Key 与 X-Trace-Id。
3.7 测试：Vitest 与 Vue Test Utils 覆盖：候选表、差异视图、确认对话框的全部状态、INFEASIBLE 与 TIMEOUT 的文案与"无采纳按钮"、错误码到提示的映射、
    时间线条目与背景条目的生成（用 examples）。Playwright 主线（E1 的 UI 部分）对真实运行的栈执行。
    定向检查：npm run lint、npm run test、npm run build。

# 阶段 4：栈脚本与端到端
4.1 docker-compose.yml 只含固定版本的 PostgreSQL；.env.example 列出变量名，不含真实值。
4.2 tools/p7_stack.py：up、down、health、wait；依次启动 PostgreSQL、FastAPI（P7_LLM=fake）、Spring、前端预览；可重复运行，停止时清理子进程。
4.3 tools/e2e_p7.py：按第六节 E1–E10 中可由脚本驱动的场景执行；用 generate_instance 固定参数生成实例（保证初始可行，记录参数）；
    并发场景用线程同时发请求；提交后拉取计划与实例，用 scheduler_core 的 validate 独立重验；
    查询数据库核对状态；结果经 ArtifactStore 写入 artifacts/runs/experiment/p7_local_demo/<run_id>/（不入库）。
4.4 README 增加"本地演示"一节：前置、启动、演示步骤、已知限制。

# 停止条件
遇到下列情况立即停止该阶段并在交接单写 NEEDS-DECISION 或 NEEDS-ENV：许可证不明或为 GPL、LGPL、AGPL、EPL；需要改动 P1–P6 既有行为才能继续；
需要创建 DeadlineAuthorization 才能让某场景通过；环境缺项；契约与 P6 实际能力冲突。

# 验收命令（真实输出写入交接单）
第六节"检查命令"全部；其中统一检查由 root 最后统一运行一次，你自检时按阶段运行定向部分，不重复全量。

# 验收标准
E1–E10 全部有真实运行证据（脚本输出、数据库状态、Playwright 结果），替身层逐项标注验证边界；
主线提交的计划经独立校验器重验通过；确认与幂等路径全部有断言；同实验室任意时刻 RUNNING ≤1；
TIMEOUT 无"不可行"表述，INFEASIBLE 无采纳入口；无 DeadlineAuthorization 创建；契约与 OpenAPI 文件一致；
依赖已核实固定并登记；diff 只含允许文件；无新增 skip 或 xfail；无密钥与构建产物入库。

# 交接
公共前言 H 格式，另附：阶段 0 读取结论与依赖核实表（含许可证）；E1–E10 对照表（每项：脚本、测试名、结果、替身说明）；
契约与实现的差异（如有）；已知限制（无认证、会话不跨进程保证、真实 DeepSeek 未验证、仿真控制台未实现等）；行数表；模型、推理档、fork 模式。
```

---

### 八、独立审查提示词

```text
[附公共前言、增量 v002、契约 CB-P7（本文件第三节）] 运行配置：gpt-6.2-sol，推理 low，fork_turns=none。
角色：P7 独立 G3 审查。只读，只写 docs/agents/handoffs/p7-review.md；探针与临时库放仓库之外或独立的测试 schema；不读作者会话。
只做针对性复核，不重复 root 的统一检查；如发现问题给出可复现步骤。必要返工由你定向复验，不重做全量。

审查项
1 范围与规范：diff 只含第四节允许的路径；scheduler_core、simulator、P6 agent 既有行为、validator、docs/source、ADR 未变；
  无 Kaiwu、QUBO、第二求解器；无新增 skip 或 xfail；无 node_modules、target、dist、密钥入库；条件限定修改（如有）为最小且有测试。
2 依赖与许可证：独立核实各依赖的版本、官方 API、许可证与兼容性，抽查传递依赖许可证；vis-timeline 的版本与许可；有无 GPL、LGPL、AGPL、EPL 或不明项。
3 契约一致：逐条对照第三节与 apps/contracts/backend-api.md、OpenAPI 文件、examples 和实际响应；错误码与 HTTP 状态；信封、追踪头、幂等头；
  Spring 未重新序列化计划、哈希来自 FastAPI；时间换算只在 FastAPI。
4 确认协议：自行用 curl 或脚本复现：无确认（428）、PENDING、已消费、过期、载荷被改、级别不符、实验室不符、基础版本不符；
  消费与动作同一事务（制造动作失败后确认仍可用）；事件注入同样受 L1 约束；提交与回滚受 L2 约束。
5 作业队列与并发：确认部分唯一索引与 SKIP LOCKED 与实验室行锁都存在且生效；自行并发注入与认领，
  采样验证同实验室 RUNNING ≤1、不同实验室可并行；运行中事件进入下一批；未决作业阻塞认领并可 discard；启动恢复；INVALID_EVENT 处理；
  提交后未决作业 STALE 且事件释放。
6 版本与提交：STALE_BASE_VERSION；提交前 Spring 再调 validate；校验失败不入库；幂等重放与同键不同体；回滚成功与 ROLLBACK_INFEASIBLE；
  版本号连续；所有决定类动作写 decision_log。
7 业务语义：f3 为 Σ end_i；严格截止；松弛仅 NEGOTIABLE、代价单位为 任务权重×截止期延后槽数、hypothetical=true、无采纳端点、界面无采纳按钮；
  grep 与阅读确认无代码创建或改绑 DeadlineAuthorization；TIMEOUT 不诊断且不宣称不可行；INFEASIBLE 在 minimal=false 时不宣称不可约。
8 校验门禁：展示的候选均 validation.passed；提交的计划由你自己用 scheduler_core 的 validate 对 plan_version 中的 plan 与 instance 重验；
  检查 E8 的替身仅限单元与集成层并已标注。
9 LLM：确认 LLM 输出均经 Pydantic 与语义校验；替身的边界说明；未宣称验证了真实 DeepSeek 或跨进程恢复。
10 前端：对照第 1.2 节的保留范围；vis-timeline 的设备分组、任务条目与窗口背景条目；差异叠加；INFEASIBLE 与 TIMEOUT 文案；错误码提示；
  仿真控制台入口页如实写"未实现"；Playwright 主线对真实栈运行。
11 端到端复核：按 README 自行启动栈并运行 tools/e2e_p7.py 与 Playwright 主线，记录真实输出；
  E1–E10 每项核对交接单对照表中的证据；artifacts 记录的 manifest 与产物。
12 限制披露：无认证、会话不跨进程保证、真实 DeepSeek 未验证、TASK_OVERRUN 不支持、仿真控制台未实现、完整容器化未做；是否如实写入。
结论 ACCEPT / REWORK / ESCALATE；发现列表（严重度、文件:行、证据、复现步骤）；探针与复核的真实输出；未能核实项；模型、推理档、fork 模式。
```

---

### 九、需要用户裁决的事项（均有推荐，回复"按推荐"即可）

- U1 认证。推荐 P7 不做真实登录与角色。actor 为自报字符串，仅写审计，L1 与 L2 是协议级二次确认，不是身份认证；真实登录留到后续。
- U2 未决作业是否阻塞后续作业。推荐阻塞：一个实验室的重规划结果出来后，必须提交或放弃，才开始下一批，这样每个作业的基础版本一致。代价是 INFEASIBLE 与 TIMEOUT 也要手动放弃才能释放事件。备选是新事件到达时自动取代旧作业，但会让用户的选择被不断重置。
- U3 回滚的含义。推荐：以旧版本的计划为内容，在当前实例上经独立校验器通过后创建新版本，不能通过则拒绝（常见于已有后续事件之后），不恢复旧实例。这是业务语义，请你确认。
- U4 界面范围缩减。接受第 1.3 节的缩减清单。
- U5 真实 DeepSeek。推荐自动验收用确定性替身，手工冒烟可选且不计入验收；若你要求验收必须含在线调用，需要密钥与网络，且结果受模型波动影响。

不需要你裁决、由工程推荐的事项：Spring JDBC 不用 ORM（记 ADR）；Flyway；轮询式工作线程；部分唯一索引加 SKIP LOCKED；jsonb 存计划与实例；契约样例由 Python 生成；视图 DTO 由 FastAPI 提供；幂等表；合并窗口 500 毫秒；确认有效期 15 分钟；批大小 50。

环境提醒：真实 PostgreSQL 是硬要求。若本机没有 JDK、Node、Docker 或浏览器，需要你先安装，这是环境缺口，不是设计问题。

---

### 十、流程与真实限制

流程：root 审 G1 → 派发实施 → 一次独立审查（返工由同一审查者定向复验）→ root 最后运行一次统一检查与 P7 端到端验收 → 普通同步并打验收标签。

真实限制（写入 README 与交接单）：

- 无登录，actor 自报。
- FastAPI 会话状态不保证跨进程恢复。
- 真实 DeepSeek 在线行为未验证，E2E 使用替身。
- TASK_OVERRUN 事件不支持，仿真控制台未实现。
- 单个 Spring 实例的队列已验证，多实例认领未验证。
- 浏览器只验证 Chromium，无压力测试。
- 完整容器化未做。

提醒：P7 的最大风险是一个低推理档的实施者同时驱动三套技术栈。所以提示词强制分四个阶段、每阶段有定向检查和停止条件。如果你觉得第一次派发仍然太大，最安全的拆法是 root 在 G1 时把"阶段 1–2（后端与队列）"与"阶段 3（前端）"拆成同一工作包内的两次提交点，但验收仍在包末统一进行。
