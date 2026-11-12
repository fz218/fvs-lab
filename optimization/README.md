# GateANN 选择率感知搜索预算补充实验

这是课程基础实验之外的独立扩展。课程固定源码、索引和原有 30 行基线结果不被改写。

## 实现内容

- `include/selectivity_budget.h`：从 Base CSR 元数据统计每个标签匹配的向量数，重复标签每个节点只计一次，值为零的项不计入。
- 对课程单标签查询，选择率为 `match_count / base_size`，不读取 Ground Truth 或 Low/Medium/High 分桶名称来选择预算。
- 查询预算为 `min(8192, round_up_64(max(320, ceil(32 / selectivity))))`。零匹配选择率使用预算上限；多标签查询明确拒绝使用单标签频次估计交集。
- `prepare_source.py`：从固定版本的 MIT 授权 GateANN 查询入口生成独立源码，采用严格的一次性替换并输出源码 SHA-256。
- 原型只改变每条查询传给 `pipe_search` 的 L，不更改索引、Graph Tunneling、过滤谓词或邻接数。
- 输出未取整的整批查询计时、每条查询的实际预算、标签频率、Recall、I/O、有效返回数及延迟，保留完整运行命令和日志。

参数 32 表示预算设计中的启发式匹配曝光目标，不保证恰好访问或返回 32 个有效候选，也不是目标 Recall 的数学保证。

## 环境与复现

需要课程仓库、课程统一数据集与已校验的预构建索引。把本工程的 `optimization/` 目录放到课程仓库根目录。

1. 按课程脚本准备 GateANN 固定提交 `71e87cbf0e25c0400c0109dd25a64a7c4dccc9dd`，应用课程 AIO 兼容补丁并完成 Release 构建。
2. 在 Linux 的课程仓库根目录运行：

```bash
bash scripts/prepare_gateann.sh
bash scripts/check_dataset.sh
bash scripts/check_indexes.sh
bash optimization/build.sh
python3 optimization/run_experiments.py \
  --experiment-id adaptive-reproduce-001 \
  --repeats 3 --target 32 --ceiling 8192
```

`build.sh` 链接课程构建好的 `systems/GateANN-public/build/src/libgateann.a`，在独立的 `optimization/build/` 目录生成新二进制，不修改上游查询源码或覆盖上游可执行文件。默认构建使用与本次 x86-64 AVX2 机器一致的编译宏；其他架构需调整 AVX 宏，不能直接搬运本机构建的二进制。

实验文件写入 `course_runs/optimization/<experiment-id>/`。每次使用新 ID，已存在的结果目录会拒绝覆盖。

## 对照设计

三个组为 `fixed320`、`fixed_max`（8192）和 `adaptive`。Low、Medium、High 三档各 200 条查询，每组 3 个独立进程重复，共 27 次运行；每轮对 9 个配置采用固定随机种子洗牌。

三组都加载相同的标签频率表，并采用同一入口、相同计时和日志机制，使频率初始化与审计开销保持可比。Query Phase 不包含索引、频率表加载；子进程总耗时与峰值 RSS 另行报告。每条查询调用不使用额外应用缓存。

27 次进程重复复用相同查询，不是 27 组独立数据样本。只比较同批补充实验的控制组和实验组；不能直接把本次延迟与十月基础实验的绝对延迟拼接作加速比。

## 检查与解释

`build.sh` 自动执行 C++ 单元测试，包括预算上下界、零选择率、非法参数、CSR 重复标签和零值项、多标签拒绝等。实验脚本校验每次 200 条查询、每标签 40 条、匹配数与课程标签清单一致、逐查询 Recall/I/O 与聚合输出一致。

报告需要同时呈现 Recall、延迟、I/O 和内存。自适应策略可能通过增加计算和 I/O 提高质量；与大预算对照比延迟下降时，如果 Recall 也下降，不能称为严格等质量加速。

## 来源

上游：<https://github.com/GyuyeongKim/GateANN-public>，固定提交见上。生成的查询入口派生自其 `tests/search_disk_index_yfcc.cpp`，上游许可证保留在 `LICENSE.upstream`。

课程入口：<https://gitee.com/wei-fangyu/fvs-course-lab>。本工程不分发课程数据、预构建索引、上游完整源码或编译产物。
