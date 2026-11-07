# Cache 映射方式与替换策略对命中率的对比实验

本目录已完成实验，采用自写 Python Trace 模拟器。先打开 **[实验报告.html](实验报告.html)** 查看完整方法、结果、图表和解释。HTML 内嵌全部图像，可单独离线分享。

## 已完成内容

- 直接映射、2/4/8 路组相联、全相联，比较 LRU、FIFO、Random。
- 12 条 Trace，831,296 条原始访存记录。8 条受控合成，4 条来自实际运行 C 程序的显式数组插桩。
- 主实验 4 KiB 容量、64 B 块；补充容量、块大小和预热实验。
- 共 768 次仿真，54,342,144 次累计块探测，300 组汇总。
- Random 对有替换选择的配置采用 10 个种子，保留逐种子数据和均值的 95% t 置信区间。
- 16 项测试通过，其中包含 120 组配置与独立时间戳模型的交叉核对。
- 7 张 PNG 图及对应 SVG；原始 CSV、参数和 Trace 哈希齐全。

已制作 [课堂汇报 PPT](presentation/output/Cache映射与替换策略_小组实验.pptx)，共 16 页，含 2 页附录及逐页讲解备注。文字、表格和图表可编辑。

## 主要结果

以下除注明外，均为 4 KiB / 64 B / 4 路，主实验从空 Cache 开始：

| 对比 | 命中率结果 | 条件解释 |
|---|---:|---|
| 两块同组循环 | 直接映射 0%，2 路 LRU 99.994% | 路数足够时解除冲突 |
| 热点混合 | LRU 86.096%，FIFO 78.725% | LRU 保留近期被访问的热点 |
| 五块争用四路 | LRU/FIFO 0%，Random 59.998% ± 0.110 pp | Random 打破循环淘汰；± 为 95% 均值 CI 半宽 |
| 矩阵转置 | 朴素 46.875%，8×8 分块 85.059% | 相同显式数组读写次数，顺序改变 |
| 65 块循环、64 块容量 | 直接映射 96.734%，全相联 LRU 0% | 受控反例：相联度收益不是逐 Trace 的单调保证 |

命中率来自本模型，不代表真机加速比。完整适用条件、随机统计口径及反例推导见报告。

## 复现

核心模拟器只用 Python 标准库，建议 Python 3.10+。生成程序 Trace 需要系统 cc（Clang 或 GCC）。

~~~sh
cd "/Users/yhx/Desktop/大三上/计算机系统结构/SCU-Computer-Architecture-Experiments/cache-lab"

# 正确性检查
python3 -m unittest -v test_cache_sim

# 生成 Trace、编译运行 C 内核并执行全部实验
python3 run_experiments.py --regenerate

# 已有 Trace 时可直接复跑全部配置
python3 run_experiments.py

# 核对保存数据、种子、源码/Trace 哈希和单配置 CLI 重放
python3 audit_results.py
~~~

绘图和重新生成报告需 matplotlib：

~~~sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python make_report.py
~~~

本机 Python 默认 CA 证书路径缺失时，安装可指定系统证书，不必关闭 HTTPS 验证：

~~~sh
.venv/bin/python -m pip install --cert /etc/ssl/cert.pem -r requirements.txt
~~~

requirements-lock.txt 保存本次绘图环境实际安装版本。Windows 激活路径改为 .venv\Scripts\python.exe；中文图表需要系统提供中文字体。
代码会优先选择 macOS Arial Unicode 或 Linux Noto Sans CJK，其他平台可在 make_report.py 字体列表中指定字体路径。

### 单配置运行

~~~sh
python3 cache_sim.py traces/hot_cold.trace.gz --capacity 4096 --block-size 64 --ways 4 --policy LRU --classify
python3 cache_sim.py traces/cycle_5.trace.gz --ways 4 --policy Random --seed 3
python3 cache_sim.py traces/capacity_cycle.trace.gz --ways full --policy LRU
~~~

Trace 格式每行“R|W 字节地址 字节数”，地址支持十进制或 0x 前缀十六进制，支持 # 注释和 gzip。例如：

~~~text
R 0x100000 4
W 0x200000 4
~~~

参数 --warmup 4096 保留前 4096 次块探测产生的 Cache、随机数和影子 Cache 状态，但不计其统计。
全相联的路数等于容量除以块大小。主实验中直接映射没有替换选择，因此不为 Random 重复 10 次。

## 文件结构

| 文件或目录 | 用途 |
|---|---|
| 实验报告.html | 自包含的完整中文实验报告 |
| cache_sim.py | 核心模拟器与 CLI |
| kernels.c | 行/列遍历、朴素/分块转置及正确性校验 |
| generate_traces.py | 合成序列与 C 插桩 Trace 生成 |
| run_experiments.py | 声明参数网格并执行实验 |
| test_cache_sim.py | 手算、边界、独立模型交叉验证 |
| audit_results.py | 结果与哈希完整性核对 |
| make_report.py | 从 CSV 生成图表与报告 |
| traces/ | 12 个压缩 Trace、清单与哈希 |
| results/raw_runs.csv | 768 次逐种子原始记录 |
| results/summary.csv | 300 组统计，命中率单位为百分数，标准差/CI 为百分点 |
| results/ppt_key_results.csv | 主实验的 180 组数据，附中文名称 |
| results/parameters.json | 完整固定参数与统计口径 |
| results/run_metadata.json | Python、平台、编译器版本及源码哈希 |
| results/validation.txt、results/audit.json | 验证记录 |
| figures/ | 7 张 PNG 及 7 张 SVG |

CSV 用 UTF-8 BOM 编码，便于用 Excel 打开。raw_runs.csv 的 hit_rate 是 0–1 比率，summary.csv 的 hit_rate_pct 是 0–100 百分数。
空白的 3C 字段表示未对 FIFO/Random 做参照分类，并非测得零次。

## 方法边界

1. 数据容量不含标签和替换元数据；模型为单级 D-Cache，写回、写分配、无预取。替换统计不含结束时强制刷回。
2. 程序 Trace 只记录显式数组访问，使用固定逻辑地址。初始化、校验、指令、栈及编译器额外访存不在范围内。
3. 所有主实验访问为对齐 4 B，不跨块。工具支持跨块，但指标按块探测统计。
4. 3C 仅在 LRU 的实际失效上，以相同容量全相联 LRU 作为参照。目标可能命中而影子失效，跨配置的容量类计数不必相等。
5. 随机置信区间仅反映替换种子变化，未覆盖不同工作负载或不同地址布局。没有把人为设计的 12 条 Trace 汇总为一个“综合性能分数”。
6. 相联度、精确 LRU 的硬件开销和命中延迟未建模，不将命中率直接换算为真机加速比。

## 课程与参考

- 本地课件《第5章 存储层次.pptx》：13–21 页映射，25–27 页替换，29–31 页写策略，36/44–47 页性能，49–55/60 页失效及优化。页码按 PPT 从 1 开始。
- [Dinero IV 官方页面](https://pages.cs.wisc.edu/~markhill/DineroIV/)：核实 Trace 驱动模拟与计时/功能模拟的边界。本次使用自写模拟器，未声称执行 Dinero IV。
