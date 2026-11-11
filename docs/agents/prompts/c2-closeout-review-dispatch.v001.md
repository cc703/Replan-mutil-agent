# C2 收尾独立复审实际派发

2026-11-11，实际/root/c2_closeout_review，gpt-6.1-terra/high/fork_turns=none。以下为实际spawn正文。

```text
你是C2收尾独立G3 reviewer，gpt-6.1-terra/high/fork_turns=none，cwd D:/Default/Replan-mutil agent。未参与实施/规划，只写docs/agents/handoffs/p1-c2-review.md（追加最终复审节，保留既有审查历史）。其他源码/测试/进度/Git只读。用户已恢复Claude合作，Claude消息86完整计划和G3提示词保存在docs/work-packages/p1-c2-claude-closeout.md，root G1 PASS，必须完整读取执行。读AGENTS/工程规范/reviewer/model-policy、p1-c2.md原G1及tempv1/v2历史、两份p1-c2handoff必要上下文，verify_source。旧agent句柄已消失，因此你是独立恢复角色，不假称昨日reviewer仍运行。
已有正式G3证据：旧review完整717+1、135实例/180DAG/10007缓存键及Win安全/官方license与hash均通过，唯一当时REWORK是API docstring已补。root随后发现assign_times修改入参，本次Claude明确收尾deepcopyTask/Person+NamedTuple TimingResult，由独立/root/c2_closeout已完成并冻结。只改timing.py/generate.py/test_generate_factors.py只追加/自身handoff追加；公开generate签名、原算法及抽取顺序保持。当前G2最终718passed/1旧symlink skip、67static通过；全check后补了同一测试的release实际变化断言，单文件6passed，未新增第二测试。交接有9hashseed实测/原命令mypyduplicate错误后加项目惯例--explicit-package-bases通过；这是命令修正无配置放宽。
严格执行closeout完整独立G3清单：复审所有本包API docstrings（IO/README文档来自前次REWORK已先补，这次作者未修改，别误报超范围）；独立构造实际任务/人员（至少一个原有blocked窗口避免alias真空断言），深快照前后不变，返回mutable数据无alias且release/deadline/level及缺勤真实有变；groups/edges为ID无需对象映射但需确认不变；RNG显式消费顺序/状态比较；只读审计其他generation数据入参mutation；验证新增测试有价值且保留旧assert、不新skip、不freezegolden。自行3种hashseed×3scale复算3指定SHA，已有大矩阵无需重跑。root额外135样本修前/后全canonical合并SHA均2e976fbbb2358436b516b434d52b90dd065282bc221a30fc9f4564824b2aae9e（scale S/M/L→u .6/.8/.95→tau .25/.5/.75→seed0..4，对每个bytes取SHA digest串联再sha）。可必要差分核对，不把此替代你的alias探针。
按Claude要求定向pytest/static/一次完整check真实执行（mypy使用--explicit-package-bases避免重复模块名）；用系统临时目录放探针，pytest -p no:cacheprovider，旧cache_dir警告可如实披露，不动配置。无Git commit/push/切换/配置，不改被审文件、不读作者会话。完整有限清单做完才正式ACCEPT/REWORK/真正业务需裁决ESCALATE，勿把“尚未执行”当外部ESCALATE或最终停止点。实际发现先报root，可继续其余独立项，不代写修复。最终在你独占review文件记录明确结论、实际命令/结果/证据/平台限制、模型和9次hash。通过后root才freeze三回归锁、G5；不要自行验收同步。
```
