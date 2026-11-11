# P1-C2 缓存位置增量实际派发 v002

2026-11-10，root G1 v002 PASS后向既有/root/p1c2_implementation发送；同模型Terra/high/fork none，不新建实施会话。temp完整计划为docs/work-packages/p1-c2-temp-plan.v002.md，原v001保留历史。

```text
root G1 v002已PASS并记录p1-c2.md，立即按docs/work-packages/p1-c2-temp-plan.v002.md完整增量实施（此即实际派发正文）：你接管src/scheduler_core/instance_cache.py，将未发布io/instance_cache.py移来，调整新模块IO导入、当前新增test_instance_cache.py引用和README；删除原新文件无wrapper，不改既有C1断言，不用隐蔽导入绕过。业务/缓存行为不变，按v002验收。Windows移动先核对source/dest绝对路径都在workspace内，用单一shell/native LiteralPath操作。历史prompt不改。source方199定向但仍补计划必需反例（root要求未覆盖不可由G3代写），你可移完后跑全check一次并收尾IO/README/license register。你的IO handoff应最新G4 PASS/G1v2，不再写等待裁决。完成切片后等source补齐统一G2。
```
