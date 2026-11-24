# P7 Spring Boot 实施交接

2026-11-24。实施来源为 Claude Sonnet 5.5 Medium 提示词 v001 和 P7 工作包的 G1 工程细化。实施角色 `/root/p7_spring` 实际使用 `gpt-6.2-sol/low/fork_turns=none`。基线 `5a423d28943a6b2dde43ba02ed50441b426af407`。

## 负责范围

- `apps/backend` 提供回环 HTTP 服务，入口 `GET /api/v1/health`，默认 `127.0.0.1:8080`。通过 `P7_DB_URL`、`P7_DB_USER`、`P7_DB_PASSWORD`、`P7_SCHEDULER_URL` 和 `SERVER_PORT` 配置。打包产物为 `apps/backend/target/p7-backend.jar`。Windows 下运行中的 JVM 持有 JAR 文件句柄，先停止该 JVM 或从 artifacts 内的复制件启动，再重建。
- `V001__init.sql` 持久化实验室、确认、事件、作业、版本、幂等、审计和对话条目。V002 将候选及原生证据放入实验室和作业范围内的关系表，可从 V001 保存的候选 JSON 迁移。
- `Approval` 和 `Writes` 管理确认级别、载荷和基础版本的绑定，确认消费与事实或正式版本同事务提交。独立 FastAPI 调用出错、事实修订变化或基础版本变化时保留审批。actor 为操作审计字段。
- `Jobs` 使用 PostgreSQL 行锁和部分唯一索引实现同实验室认领、批次快照和未决阻塞。已确认事件保留原始 HTTP 契约形状，FastAPI 的槽归一化仅用于预览。作业失败或重启释放事实并保存失败信息，等后续队列或显式重试。后确认事实另外验证，提交仅应用各作业覆盖的事实。回滚按当前世界验证和归档。
- `ApiTrace` 向调度服务传递 trace，Spring JSON 日志记录公开路由形状、方法和 HTTP 状态。日志用占位符代替实验室、作业、计划和确认 ID，省略请求正文和查询参数。使用真实 FastAPI 的 POST /api/v1/labs 返回 201，响应头和 Spring JSON 行均含 p7-spring-structured-proof，并核对方法、公开路由及状态。

## 依赖和验证

- Java 17.0.18，Maven 3.9.11。官方 Maven Wrapper 3.3.4 only-script，分发 URL 固定 Maven 3.9.11，以 Maven Central SHA-512 核对的 ZIP 计算并固定 SHA-256。Wrapper 用于构建引导，Windows mvnw.cmd -v 已报告 Maven 3.9.11。
- Spring Boot 3.5.8、Spring Framework 6.2.14、Tomcat 10.1.49、MyBatis-Plus 3.5.14（MyBatis 3.5.19、MyBatis Spring 3.0.5）、Flyway 11.7.2、Log4j 2.24.3、HikariCP 6.3.3、Jackson 2.19.4、SnakeYAML 2.4、Micrometer 1.15.6 见 Maven 解析结果。上述为 Apache-2.0 栈，Flyway 许可来自固定版 parent POM。pgjdbc 42.7.8 为 BSD-2-Clause，SLF4J 2.0.17 与 checker-qual 3.49.5 为 MIT。校验为 JDK main 加 Apache-2.0 exec-maven-plugin 3.5.0。Maven 与运行 JAR 只作本地验证，分发前需按打包清单审查各自 LICENSE/NOTICE。
- Spring Web 默认的 EPL-2.0/GPL2 w/CPE `jakarta.annotation-api:2.1.1` 和默认 Logback 已排除。Tomcat 实际需要 `jakarta.annotation.PostConstruct`，因此使用同版本 Apache-2.0 的 `org.apache.tomcat:tomcat-annotations-api:10.1.49`。已核查其 Central 固定 POM、JAR 中的该 class 及 LICENSE/NOTICE，并验证替代后能启动。最终依赖树和 JAR 内容中没有被排除的包。
- `mvn -B -f apps/backend/pom.xml verify dependency:tree -DoutputFile=target/dependencies.txt` 通过。该验证只允许回环 `p7_test`，要求 `P7_TEST_DB_URL`、`P7_TEST_DB_USER`、`P7_TEST_DB_PASSWORD`。创建并清理随机 schema。使用实际 PostgreSQL 17.12 验证两实验室并发认领、单实验室作业独占、未决 TIMEOUT 阻塞、异常后审批仍可消费、单次消费和恢复后事实释放。恢复用例直接调用 Jobs.recover()，验证事务结果；实际停止并启动 Spring 进程的证明由 root 执行。
- 独立烟测用实际 FastAPI、Spring 和 PostgreSQL，在 `p7_test` 的 `spring_smoke` schema 跑通初始确认、停用、原计划不可展示、重排与 v2 提交。随后设置 `PYTHONPATH=src`、数据库环境和 `PGOPTIONS=-c search_path=spring_smoke`，运行 `uv run --python 3.11 --group dev python tools/e2e_p7.py --url http://127.0.0.1:18080 --database p7_test` 通过。记录为 `artifacts/runs/experiment/p7_local_demo/20261124-031630_5a423d2_http-db`。此轮 E2E 用确定性 LLM 替身；调度与校验均真实。
- 来源为 [Spring Boot 固定 POM](https://repo.maven.apache.org/maven2/org/springframework/boot/spring-boot-starter-parent/3.5.8/spring-boot-starter-parent-3.5.8.pom)、[MyBatis-Plus 固定 POM](https://repo.maven.apache.org/maven2/com/baomidou/mybatis-plus-spring-boot3-starter/3.5.14/mybatis-plus-spring-boot3-starter-3.5.14.pom)、[Flyway parent](https://repo.maven.apache.org/maven2/org/flywaydb/flyway-parent/11.7.2/flyway-parent-11.7.2.pom)、[Tomcat 注解固定 POM](https://repo.maven.apache.org/maven2/org/apache/tomcat/tomcat-annotations-api/10.1.49/tomcat-annotations-api-10.1.49.pom)、[pgjdbc 许可](https://jdbc.postgresql.org/about/license.html)、[Maven Wrapper 3.3.4](https://maven.apache.org/tools/wrapper/)。

## 本地边界

一次部署运行一个 Spring 实例，多个本地 worker 可并行处理不同实验室。未验多进程 Spring 共享同一 schema、真实 DeepSeek、FastAPI 进程间会话恢复、第三方依赖分发及漏洞审计。独立 G3、统一验证、Git 同步与阶段验收归 root。




## G3 返工

提交预览、候选列表和提交执行共用作业快照和候选证据的当前世界校验。L2 提交与回滚预览的幂等重放也在实验室锁内重新检查当前版本和事实。失效预览拒绝返回已缓存的候选差异或校验结果。版本详情和差异共用版本可用检查，差异两侧只要有活动版本受当前事实影响即拒绝返回分配。

设置 P7_TEST_SCHEDULER_URL 指向回环真实 FastAPI 后，原 Maven verify 额外在随机 HTTP 端口运行 CurrentPlanChecks。用真实 PostgreSQL 隔离 schema 验证正常预览、伪造哈希、冲突 L1 后的新键与同键提交预览、回滚预览重放、拒绝提交时的 L2 保留，以及活动 v2 在差异两侧均拒绝和历史差异仍可读取。无该变量时继续运行数据库事务检查。
