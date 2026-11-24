# P7 Vue 实施交接

状态：DONE。Vue 定向自检和真实本地栈 Chromium 主线通过，等待 P7 独立审查。工作包依据 Claude P7 v001（Sonnet 5.5 Medium）及 P7 卡 G1，服务合同以 `apps/contracts/backend-api.md` 和示例为准。实施配置 `gpt-6.2-sol/low/fork_turns=none`。

## 文件和用途

| 新增路径（相对于 apps/frontend） | 用途 |
|---|---|
| `index.html`、`src/main.ts`、`src/app.vue`、`src/style.css` | 中文界面、八条应用路由、实验室选择、自报操作者、样式 |
| `package.json`、`package-lock.json`、`tsconfig.json`、`vite.config.ts`、`.gitignore` | 精确依赖锁定、TS、构建与测试、回环监听、忽略产物 |
| `src/types.ts`、`src/api.ts`、`src/state.ts` | Spring 对外 DTO、带幂等和追踪头的浏览器请求、错误中文提示、北京时间 |
| `src/pages/import.vue`、`inventory.vue`、`sim.vue` | 实例 JSON 文件或粘贴导入、设备人员任务只读表、手工注入入口 |
| `src/pages/plan.vue`、`versions.vue` | 当前计划及需重规划状态、历史证据、版本差异、审计日志、L2 回滚 |
| `src/timeline.ts`、`src/components/timeline.vue`、`diff.vue` | 设备行、任务范围、关闭/维护/故障/运行背景、原新安排叠加和差异表。模板以 DOM textContent 使用不可信文本 |
| `src/pages/workbench.vue`、`src/components/event-form.vue`、`job-result.vue` | 停机、急件预览，真实异步轮询及未决阻塞，候选筛选与比较、解释、L2 提交、手工放弃或重试 |
| `src/pages/chat.vue`、`src/components/confirmation.vue` | 对话澄清、事件字段编辑、截止期通过新回合修订，统一 L1/L2 分步预览、确认、应用、拒绝和错误重试 |
| `tests/views.test.ts`、`confirmation.test.ts`、`mainline.spec.ts`、`playwright.config.ts` | 差异、候选、诊断、确认交互与真实 Chromium 主线 |

浏览器只通过 Spring `/api/v1` 通信。Vite dev 与 preview 均绑定 `127.0.0.1`，代理目标取 `P7_SPRING_URL`（默认 `http://127.0.0.1:8080`）。Playwright 读取 `P7_FRONTEND_URL`（默认 `http://127.0.0.1:5173`）。初始计划走同一候选 L2。时间线与业务显示使用服务生成的 ISO 时间，不自行计算时间槽。P6 事件草案可编辑后走常规预览，截止期草案由新的对话回合产生待确认项，沿用现有约束接口。

## 依赖与来源

2026-11-24 用 npm 官方注册表和已安装 manifest 核对固定版本、许可证与仓库；用已安装类型/API、真实构建和测试核对兼容性。Node `v24.14.1`、npm `11.11.0`，Playwright 配套 Chromium 构建号 1228（149.0.7827.55）。

| 固定版本 | 许可证 | 用途和来源 |
|---|---|---|
| Vue 3.5.30 | MIT | 界面与响应式数据，[Vue API](https://vuejs.org/api/) |
| Vue Router 4.6.4 | MIT | 路由与应用历史，[Vue Router API](https://router.vuejs.org/api/) |
| Element Plus 2.13.5 | MIT | [Button](https://element-plus.org/en-US/component/button.html)、[Dialog](https://element-plus.org/en-US/component/dialog.html) |
| vis-timeline 8.5.0 | Apache-2.0 OR MIT | 设备分组、时间窗、DOM 模板，[Timeline API](https://visjs.github.io/vis-timeline/docs/timeline/)，[官方仓库](https://github.com/visjs/vis-timeline) |
| Moment 2.30.1 | MIT | timeline 时区回调，固定 UTC+08:00，[utcOffset API](https://momentjs.com/docs/#/manipulating/utc-offset/) |
| Vite 7.3.1、@vitejs/plugin-vue 6.0.4 | MIT | [代理与预览](https://vite.dev/config/preview-options)、[Vue 编译插件](https://github.com/vitejs/vite-plugin-vue/tree/main/packages/plugin-vue) |
| TypeScript 5.9.3 | Apache-2.0 | [类型检查](https://www.typescriptlang.org/docs/) |
| vue-tsc 3.2.5 | MIT | [Vue SFC 类型检查](https://github.com/vuejs/language-tools/tree/master/packages/tsc) |
| @types/node 24.10.1 | MIT | [Node 配置和测试类型](https://github.com/DefinitelyTyped/DefinitelyTyped/tree/master/types/node) |
| Vitest 4.0.18、@vue/test-utils 2.4.6、jsdom 27.4.0 | MIT | [测试运行](https://vitest.dev/guide/)、[组件测试](https://test-utils.vuejs.org/api/)、[测试 DOM](https://github.com/jsdom/jsdom) |
| @playwright/test 1.61.1 | Apache-2.0 | [Chromium 真实浏览器主线](https://playwright.dev/docs/intro) |

锁文件检查枚举 MIT、MIT-0、ISC、Apache-2.0、BSD-2-Clause、BlueOak-1.0.0、Apache-2.0 OR MIT、CC0-1.0 和 BSD-3-Clause 声明。Moment 直接依赖已由 vis-timeline 使用的同一固定版本，用于明确声明时区 API。无新增外部运行服务。无发行级全量第三方义务审计。

## 验证

- `python tools/verify_source.py`：3 份已核验原文的字节、行数、SHA-256、编码、换行及逐批验证全部 PASS。
- `npm run lint`：`vue-tsc --noEmit`，退出码 0。
- `npm run test`：`Test Files  2 passed (2)`；`Tests  10 passed (10)`。
- `npm run build`：`vite v7.3.1 building client environment for production...`，`✓ 1640 modules transformed.`，退出码 0。懒加载 vis-timeline chunk 约 622 kB（gzip 183 kB），超过 Vite 默认 500 kB 提示阈值。
- `$env:P7_FRONTEND_URL="http://127.0.0.1:15173"; npm run test:e2e`：`ok 1 tests\mainline.spec.ts:6:1 › E1 导入、初始计划提交、停机重规划和正式版本更新 (7.8s)`，`1 passed (8.3s)`。确认实验室 `9a212015-9f49-42bb-93eb-642e57279730` 的 `active_version_no` 为 2。浏览器首轮完成 v1 后在选择器名称上超时，增加设备的显式可访问名称后从新实验室重跑通过。
- `python tools/check_repo_layout.py`：`Layout: PASS`；`git diff --check` 退出码 0。

源码行数（不含锁文件）：应用壳与公共 TS 314 行，样式 320 行，组件 292 行，页面 464 行，测试 224 行。最长业务文件 `workbench.vue` 141 行。

| 验收编号 | Vue 证据和覆盖边界 |
|---|---|
| E1 | Chromium `tests/mainline.spec.ts`，导入、初始 L2、停机 L1、候选变化叠加、正式 L2、v2 状态与审计入口。浏览器端无拦截或数据替身 |
| E2、E3、E4 | 前端单元层模拟 API 响应，测试基线变化、过期、级别与重复冲突文案，以及分步确认与失败重试保留幂等键；协议真实状态由联合验收覆盖 |
| E5 | 真实轮询表现见 E1；队列并发隔离由联合验收覆盖 |
| E6 | `views.test.ts` 单元呈现预算、冲突核和假设证据文案，以及不可采纳；求解实况由联合验收覆盖 |
| E7 | 对话接线与真实 P6 解析由联合验收覆盖。浏览器 E1 不调 LLM |
| E8 | Vue 单元断言拒绝假定校验未通过候选；真实提交的独立重验由联合验收覆盖 |
| E9、E10 | 版本差异、回滚与审计入口已接线；数据库及回滚验证由联合验收覆盖 |

与合同的偏差：无。仿真控制明确未实现；UI 引导手动注入。系统限制为无登录、P6 会话不保证跨进程恢复、不支持 TASK_OVERRUN、未验证真实 DeepSeek、仅 Chromium 验收、无完整容器部署。

未决问题：无 Vue 专项阻塞。需裁决问题：无。下一步：由 root 汇总 E1–E10，并交独立 G3 复核。未提交或推送。


## G3 定向返工

L2 弹窗复用任务差异表，展示提交的 `preview.diff`、回滚的 `preview.changes`、服务返回的 `f1/f2/f3`（含零值）和 `preview.validation`。独立校验失败或缺失时禁用确认，保留拒绝与关闭。回滚按服务器的当前事实校验结果展示。

运行 `npm run lint`、`npm run test`（`Test Files 2 passed (2)`、`Tests 13 passed (13)`）与 `npm run build`（退出码 0，时间线 chunk 体积提示仍在）。使用 `P7_FRONTEND_URL=http://127.0.0.1:15413` 对真实栈运行 `npm run test:e2e`，`1 passed (8.6s)`，真实候选 L2 在确认前断言独立校验、急件目标和重规划任务行。回滚变化、校验失败及缺失证据的分支由组件模拟响应定向覆盖。已通知原 G3 审查者复验。
