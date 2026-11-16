# P2-1 API/依赖实施交接

基线 a994cd0；API/依赖专项，计划来源 temp v001，G1/G4 见工作包卡。`solve_initial.py` 提供原签名及 detailed 结果，PENDING 限制、实例空计划预检（只排除 MISSING_ASSIGNMENT）、参数检查和所有正式计划独立 validate。空任务也走正式校验。模型权重检查与求解交 solving 专项。模型无效原接口抛异常，UNKNOWN/INFEASIBLE 返回 None。

`pyproject.toml` 和 `uv.lock` 添加 OR-Tools 9.15.6755；`uv add --no-sync --no-upgrade`、`uv sync --locked --python 3.11 --group dev`，实际导入版本 9.15.6755。与 HEAD lock 比较旧版本均不变，新增 absl-py 2.5.1、immutabledict 4.3.1、ortools 9.15.6755、pandas 3.1.1、protobuf 6.33.6、python-dateutil 4.0.0、tzdata 2026.6。Windows cp311 wheel 已下载并查内容；详细许可信息、尚未核实项、用户批准本地运行及对外发行前另审记录于 dependency-register。未提交 wheel。无安全审计。

`python tools/verify_source.py` PASS；定向 `uv run --locked --python 3.11 --group dev ruff check src/scheduler_core/solve_initial.py` 和相同方式 mypy 均 PASS。初次安装前 mypy 因未安装 ortools 报 import-not-found，安装后通过。联合业务测试和全量检查由测试专项与 root 运行；独立 G3 待做。
