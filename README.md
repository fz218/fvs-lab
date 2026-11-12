# 过滤向量检索课程实验补充实现

本工程包含 GateANN 选择率感知搜索预算的代码、测试、复现说明和脱敏结果。基础实验的两套系统、固定参数和原有 30 行结果不被改写；新增实现属于补充扩展。

入口与完整操作步骤见 [optimization/README.md](optimization/README.md)。把 `optimization/` 放到已完成课程准备的仓库根目录，运行 `bash optimization/build.sh` 和 `python3 optimization/run_experiments.py`。

## 文件说明

- `optimization/`：源代码、独立构建脚本、C++ 测试和复现说明。
- `results/baseline.csv`：原始 30 行基础结果，日志路径已改为课程根目录相对路径。
- `results/optimization.csv`：27 次补充查询进程的聚合结果。
- `results/summary.csv`：三轮中位数和最小/最大值。
- `results/query_audit/`：逐查询的标签 ID、选择率、实际 L、Recall、延迟、I/O 与有效结果数。
- `results/commands/`：运行命令、退出码和原始输出；机器路径统一替换为 `${LAB_ROOT}`。
- `results/validation.json`：对 5400 条逐查询记录的独立一致性检查。
- `UPLOAD_MANIFEST.json`：上传文件的 SHA-256 与大小清单。

本工程不包含学生个人信息、凭据、数据集、向量、Ground Truth、预构建索引、上游完整源码、编译文件、内部聊天或文档制作记录。结果来自特定的 WSL2 单机环境，性能比较应同时考虑 Recall，不能把质量变化忽略为等质量加速。

课程仓库：<https://gitee.com/wei-fangyu/fvs-course-lab>。
上游 GateANN：<https://github.com/GyuyeongKim/GateANN-public>；派生代码的 MIT 授权见 `optimization/LICENSE.upstream`。
