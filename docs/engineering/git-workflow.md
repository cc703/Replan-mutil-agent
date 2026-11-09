# Git 工作流与进度同步

版本：v001。仅总设计师执行提交、推送、分支切换和 Git 配置。专项会话交付文件与交接单。

## 分支与所有权

当前仓库 origin 为 https://github.com/cc703/Replan-mutil-agent.git，启动时为空仓；当前集成分支为 `codex/p0-governance`。Git 作者在本仓库局部配置为 chm，邮箱保留于本地 Git 配置，不在进度文档反复展示。

后续分支使用 `codex/<phase>-<topic>`。同一共享工作树内最多三个实施会话，按互斥文件清单协作，不各自 checkout。需要多分支时总设计师显式建立并登记隔离工作树。空仓可以直接提交首个实际交付；只有确需统一基线时才创建空提交，未执行就不得宣称存在。

## 每包提交与同步

1. G2/G3 完成；解决 G4，或说明 N/A。
2. 总设计师检查实际 diff、文件用途、规则一致性和敏感信息；不把整仓 `git add .` 当审核。
3. 在同次交付更新 [PROGRESS.md](../progress/PROGRESS.md)、工作包交接和 CHANGELOG；验收、同步两字段分别记录真实状态。
4. 运行 P0 `python tools/check.py`（就绪后可用 `uv run --python 3.11 --group dev python tools/check.py`）；检查失败不提交为验收完成。
5. 显式暂存当前工作包文件，查看 staged diff，提交 `type(scope): subject`，scope 使用工作包编号，例如 `docs(p0-a): establish governance standards`。
6. 首次推送 `git push -u origin codex/p0-governance`；后续普通 push。禁用强制推送、改写历史和未经请求的仓库可见性/权限变更。
7. 核对本地提交 SHA 与 `git ls-remote origin refs/heads/<branch>`，仅一致时确认已同步。
8. 每个完成工作包都及时同步。并行包已在磁盘但尚未提交的文件需在进度里说明所有者，不得混入当前包。待全部工作包交付后工作区应干净。

## 状态真实性与哈希

工作包可先工程验收通过、同步待执行；尚未 push 成功且核验之前，状态保持 IN-REVIEW，不能写成 ACCEPTED/已同步。提交哈希不能自引用：同次进度写提交主题或工作包 ID，提交后由 git log 查询；下一次进度提交再记录上一交付的真实 SHA。同步回执记录在下一次进度更新，不能为填当前提交 SHA 反复 amend。

推送失败时保留本地提交，记录失败原因、远端状态、待重试动作；不以本地 commit 冒充 GitHub 同步。需要凭证、远端权限或仓库策略由用户处理时说明具体阻塞。

## 集成、标签与回滚

P0 全部验收且同步成功后，由总设计师决定是否将集成分支通过普通合并进入 main，先核对远端现有历史，不覆盖 main。仅在完整验收有证据后才可创建 `p0-accepted` 标签；缺源文档或未决设计时不能提前标记。

已公开提交的修复使用新提交，通常通过 revert 形成可审计回滚；破坏性回退、强制推送和受保护文件删除需用户明确决定。回滚也须 Claude 提供计划、提示词和影响分析，随后更新进度与同步。
