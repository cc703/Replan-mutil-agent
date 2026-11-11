# ADR 0007：NumPy Windows 运行依赖

状态：ACCEPTED；2026-11-10（Asia/Shanghai），用户 G4 明确裁决。适用 P1-C2，代码实施仍受既定 G1/G2/G3/G5 约束。

## 背景与对象

原设计要求 NumPy Generator/PCG64。专项读取了 NumPy 2.4.6 官方 CPython 3.11 Windows wheel 的实际发行许可证，发现捆绑 GCC runtime 的 `GPL-3.0-or-later WITH GCC-exception-3.1` 及 OpenBLAS/LAPACK 等归属义务；根源码 BSD 不能代表整个 wheel。按项目开源政策提交 G4，而非自行推定豁免。

对象：`numpy-2.4.6-cp311-cp311-win_amd64.whl`，SHA256 `1e254a00cdf42b1e4d5b3d68d33af63268d41340d8885df2ab6470f2e1500147`。官方元数据：https://pypi.org/pypi/numpy/2.4.6/json 。实际发行包检查与后续许可记录见 `docs/agents/handoffs/p1-c2.md` 及依赖登记；这不是项目对未来分发方式的法律结论。

## 选项与用户决定

- 推荐：仅作为开发/运行依赖安装并固定版本，记录完整附带许可证；未来打包分发二进制前另行审查。
- 备选：暂缓 NumPy，暂停依赖它的实现；不得擅改原设计为其他随机库。

用户对上述具体对象与推荐范围答复：“批准按建议使用，继续开发”。总设计师据此解除本次安装与实现的许可门禁，通知原实施专项继续；不重复请求此授权。

## 边界

依赖锁及来源可入库，wheel、环境和缓存不入库。不修改或重新打包依赖，不为本项目选择 LICENSE，不改变仓库可见性。实际二进制分发前重新核对附带许可证、归属、NOTICE 与适用义务；本裁决不提前批准未知分发方式。后续版本或捆绑内容改变须重新核实。
