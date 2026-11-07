"""Render publication-friendly result charts and a self-contained Chinese report."""
import base64
import csv
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "build/matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(ROOT / "build/cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

for p in ["/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
          "/Library/Fonts/Arial Unicode.ttf",
          "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]:
    if Path(p).exists():
        font_manager.fontManager.addfont(p)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=p).get_name()
        break
plt.rcParams.update({"axes.unicode_minus": False, "font.size": 12,
                     "axes.titlesize": 17, "axes.labelsize": 13,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "svg.fonttype": "path", "figure.facecolor": "white",
                     "savefig.facecolor": "white"})
FIGS = ROOT / "figures"
FIGS.mkdir(exist_ok=True)
rows = list(csv.DictReader((ROOT / "results/summary.csv").open(encoding="utf-8-sig")))
manifest = json.loads((ROOT / "traces/manifest.json").read_text())
metadata = json.loads((ROOT / "results/run_metadata.json").read_text())
labels = {w["name"]: w["label"] for w in manifest["workloads"]}
colors = ["#1769aa", "#e08d24", "#228879", "#8b61a9", "#d15264", "#45566c"]
policies = ["LRU", "FIFO", "Random"]


def query(workload, experiment="main", ways=4, policy="LRU", capacity=4096, block=64):
    matches = [r for r in rows if r["experiment"] == experiment and r["workload"] == workload
               and int(r["ways"]) == ways and r["policy"] == policy
               and int(r["capacity_bytes"]) == capacity and int(r["block_bytes"]) == block]
    assert len(matches) == 1, (workload, experiment, ways, policy, capacity, block)
    return matches[0]


def rate(*args, **kwargs):
    return float(query(*args, **kwargs)["hit_rate_pct"])


def save(fig, name):
    fig.savefig(FIGS / f"{name}.png", dpi=180, bbox_inches="tight")
    fig.savefig(FIGS / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def charts():
    names = list(labels)
    ways = [1, 2, 4, 8, 64]
    a = np.array([[rate(w, ways=k) for k in ways] for w in names])
    fig, ax = plt.subplots(figsize=(11.5, 8.6), layout="constrained")
    im = ax.imshow(a, vmin=0, vmax=100, cmap="Blues", aspect="auto")
    ax.set_xticks(range(5), ["直接映射", "2 路", "4 路", "8 路", "全相联（64 路）"])
    ax.set_yticks(range(len(names)), [labels[w] for w in names])
    ax.set_title("映射方式对命中率的影响\n容量 4 KiB，块 64 B，LRU，冷启动", pad=16)
    for i in range(len(names)):
        for j in range(5):
            ax.text(j, i, f"{a[i,j]:.2f}%", ha="center", va="center",
                    color="white" if a[i,j] > 60 else "#18334c", fontsize=12)
    fig.colorbar(im, ax=ax, label="命中率（%）", shrink=.8)
    save(fig, "01_mapping")

    names = ["hot_cold", "cycle_5", "conflict_8", "transpose_naive", "transpose_tiled", "uniform_random"]
    fig, ax = plt.subplots(figsize=(12.5, 8), layout="constrained")
    y = np.arange(len(names))
    for i, policy in enumerate(policies):
        values = [rate(w, policy=policy) for w in names]
        err = [float(query(w, policy=policy)["ci95_half_pp"]) for w in names]
        bars = ax.barh(y + (i-1)*.23, values, .21, label=policy,
                       color=colors[i], xerr=err, capsize=3, error_kw={"linewidth": 1})
        ax.bar_label(bars, labels=[f"{v:.2f}" for v in values], padding=4, fontsize=10)
    ax.set_yticks(y, [labels[w] for w in names])
    ax.invert_yaxis()
    ax.set_xlim(0, 106)
    ax.set_xlabel("命中率（%）")
    ax.set_title("替换策略没有统一赢家\n4 KiB / 64 B / 4 路；Random 为 10 个种子的均值与 95% 均值置信区间", pad=17)
    ax.grid(axis="x", alpha=.15)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", ncol=3)
    save(fig, "02_replacement")

    names = ["row_scan", "column_scan", "transpose_naive", "transpose_tiled"]
    fig, ax = plt.subplots(figsize=(10.5, 6), layout="constrained")
    values = [rate(w) for w in names]
    bars = ax.bar([labels[w] for w in names], values,
                  color=[colors[0], colors[0], colors[2], colors[2]], width=.58)
    ax.bar_label(bars, labels=[f"{v:.2f}%" for v in values], padding=6, fontsize=15)
    ax.set_ylim(0, 108)
    ax.set_ylabel("命中率（%）")
    ax.set_title("访问顺序显著改变缓存利用率\nC 程序显式数组 Trace，128×128，4 KiB / 64 B / 4 路 LRU", pad=18)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
    save(fig, "03_program_locality")

    fig, ax = plt.subplots(figsize=(10.5, 6.5), layout="constrained")
    xs = [1, 2, 4, 8, 16]
    for i, w in enumerate(["hot_cold", "uniform_random", "transpose_naive", "transpose_tiled", "column_scan"]):
        ys = [rate(w, experiment="capacity", capacity=k*1024) for k in xs]
        ax.plot(range(len(xs)), ys, marker="o", linewidth=2.4, color=colors[i], label=labels[w])
    ax.set_xticks(range(len(xs)), xs)
    ax.set_ylim(-4, 105)
    ax.set_xlabel("Cache 数据容量（KiB）")
    ax.set_ylabel("命中率（%）")
    ax.set_title("容量增加对不同访问模式的作用不同\n块 64 B，4 路 LRU；固定 Trace 与矩阵布局", pad=16)
    ax.grid(alpha=.2)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.16), ncol=3, fontsize=11)
    save(fig, "04_capacity")

    fig, ax = plt.subplots(figsize=(10.5, 6.5), layout="constrained")
    xs = [16, 32, 64, 128]
    for i, w in enumerate(["sequential", "hot_cold", "uniform_random", "transpose_naive", "transpose_tiled"]):
        ys = [rate(w, experiment="block_size", block=k) for k in xs]
        ax.plot(range(4), ys, marker="o", linewidth=2.4, color=colors[i], label=labels[w])
    ax.set_xticks(range(4), xs)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Cache 块大小（B）")
    ax.set_ylabel("命中率（%）")
    ax.set_title("增大块并不总能提高命中率\n容量 4 KiB，4 路 LRU", pad=16)
    ax.grid(alpha=.2)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.16), ncol=3, fontsize=11)
    save(fig, "05_block_size")

    names = ["sequential", "conflict_8", "hot_cold", "capacity_cycle", "column_scan", "transpose_tiled"]
    fig, ax = plt.subplots(figsize=(12, 6.5), layout="constrained")
    bottom = np.zeros(len(names))
    for i, (field, label) in enumerate([("compulsory", "首次访问"), ("capacity", "容量（FA-LRU 参照）"),
                                       ("conflict", "冲突（FA-LRU 参照）")]):
        values = np.array([float(query(w)[field + "_mean"]) / int(query(w)["accesses"]) * 100 for w in names])
        ax.bar(range(len(names)), values, bottom=bottom, color=colors[i], label=label, width=.6)
        bottom += values
    for i, v in enumerate(bottom):
        ax.text(i, v + 1.6, f"{v:.2f}%", ha="center")
    ax.set_xticks(range(len(names)), [labels[w].replace(" ", "\n", 1) for w in names])
    ax.set_ylim(0, 111)
    ax.set_ylabel("每 100 次访问中的失效次数")
    ax.set_title("用同容量全相联 LRU 解释实际失效\n4 KiB / 64 B / 4 路 LRU；三类之和等于目标 Cache 失效数", pad=16)
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=3, fontsize=11)
    save(fig, "06_miss_classes")

    fig, ax = plt.subplots(figsize=(10.5, 6), layout="constrained")
    values = [rate("capacity_cycle", ways=w) for w in ways]
    bars = ax.bar(["直接映射", "2 路", "4 路", "8 路", "全相联"], values,
                  color=colors[0], width=.57)
    ax.bar_label(bars, labels=[f"{v:.2f}%" for v in values], padding=6, fontsize=14)
    ax.set_ylim(0, 110)
    ax.set_ylabel("命中率（%）")
    ax.set_title("反例：更高相联度不保证每条 Trace 都更好\n64 个缓存块，依次循环读取 65 个连续块，LRU", pad=17)
    ax.grid(axis="y", alpha=.15)
    ax.set_axisbelow(True)
    save(fig, "07_counterexample")


def table(headers, data):
    esc = lambda x: html.escape(str(x))
    return "<div class='table-scroll'><table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + (
        "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{esc(v)}</td>" for v in row) + "</tr>"
                                        for row in data) + "</tbody></table></div>")


def image(name, caption):
    encoded = base64.b64encode((FIGS / f"{name}.png").read_bytes()).decode()
    return f"<figure><img src='data:image/png;base64,{encoded}' alt='{html.escape(caption)}'><figcaption>{caption}</figcaption></figure>"


def report():
    h = []
    h.append("""<header><p class="eyebrow">计算机系统结构 · 小组实验</p>
    <h1>Cache 映射方式与替换策略<br>对命中率的对比实验</h1>
    <p class="lead">基于自写 Trace 模拟器的已执行实验。主实验固定容量与块大小，对比映射和替换策略，并用程序访问模式解释差异。</p></header>""")
    h.append(f"<p class='summary'>12 条访问序列 · 768 次仿真 · {metadata['simulated_line_probes']:,} 次累计块访问 · 7 张图表 · 16 项测试</p>")
    h.append("<h2>1. 实验目的与课程对应</h2><p>回答三个问题：映射约束如何造成冲突失效？LRU、FIFO、Random 在不同访问模式下有何差异？容量、块大小和程序局部性如何影响这些结论？</p>")
    h.append("<p>本地资料《第5章 存储层次》是主要课程依据。现有目录未发现额外实验评分细则，以下规模和参数是本实验自行设计的控制条件。</p>")
    h.append(table(["课件页码（从 1 开始）", "对应内容", "本实验落实"],
                   [["13–21", "全相联、直接映射、组相联", "1 / 2 / 4 / 8 / 64 路等容量对比"],
                    ["25–27", "Random、FIFO、LRU", "同一 Trace 上比较三种策略"],
                    ["29–31", "写回、写分配", "统一采用写回、写分配"],
                    ["36、44–47", "命中率与平均访存时间", "只测命中率，不把它等同于执行时间"],
                    ["49–55、60", "3C、块大小、相联度", "失效参照分类和参数敏感性实验"]]))
    h.append("<h2>2. 模型与控制变量</h2>")
    h.append(table(["项目", "设置"],
                   [["Cache 范围", "单级数据 Cache；只追踪块身份、有效性、替换顺序和脏位"],
                    ["主实验容量", "4 KiB = 4096 B，仅数据容量，不包含标签与替换元数据"],
                    ["主实验块大小", "64 B，总块数 64"],
                    ["映射方式", "直接映射；2、4、8 路组相联；64 路全相联"],
                    ["替换策略", "精确 LRU；FIFO；均匀随机选择已占用路"],
                    ["写与预取", "write-back + write-allocate；按需取块，无预取"],
                    ["初始状态", "主实验每次从空 Cache 开始，计入冷启动"],
                    ["随机重复", "Random 在 2/4/8/64 路各用种子 0–9；直接映射无选择，只运行一次"],
                    ["容量扫描", "1 / 2 / 4 / 8 / 16 KiB；固定 64 B、4 路 LRU"],
                    ["块大小扫描", "16 / 32 / 64 / 128 B；固定 4 KiB、4 路 LRU"],
                    ["预热检查", "4 条代表 Trace 丢弃前 4096 次探测统计，保留 Cache 与随机数状态"]]))
    h.append("""<p>地址分解：<code>块号 = 地址 // B</code>，<code>组数 S = C / (B × A)</code>，
    <code>组索引 = 块号 % S</code>，<code>标记 = 块号 // S</code>。其中 C 为字节容量，B 为块大小，A 为路数。
    同一次比较只改变声明的变量。所有策略均优先填空路，组满后才替换；LRU 命中更新最近使用次序，FIFO 命中不改变插入次序。</p>
    <p><strong>命中率 = 命中次数 / 总块探测次数。</strong>主实验全部是对齐的 4 B 访问，在所有扫描块大小下都不跨块，因此一条 Trace 记录对应一次块探测。
    工具也支持跨块访问，届时会按涉及的块分别统计。写失效先装入块并置脏，脏块换出才计写回，结束时不强制刷回。</p>""")
    h.append("<h2>3. 工作负载与 Trace 来源</h2>")
    h.append(table(["ID / 名称", "来源", "访问次数", "生成规则"],
                   [[w["name"] + " / " + w["label"], "受控合成" if w["source"] == "synthetic" else "C 源码显式插桩",
                     f"{w['references']:,}", w["description"]] for w in manifest["workloads"]]))
    h.append("""<p>8 条合成 Trace 用来隔离空间局部性、时间局部性、同组冲突与容量压力。热点和均匀随机序列生成种子分别为 20261107、20261108，生成后对所有配置复用同一文件。
    顺序扫描与按行遍历拥有相同访问模式，保留两者是为了对照生成器与程序插桩，不能把它们当作两个独立应用样本来放大结论。</p>
    <p>4 条程序 Trace 来自实际编译并执行的 <code>kernels.c</code>。矩阵为 128×128 的 uint32，行主序存储，每种内核执行 4 轮。
    行/列遍历校验求和，两个转置实现逐元素校验输出。记录显式数组读取与写入，并将 A/B 映射到固定逻辑基址 0x100000/0x200000。
    初始化、校验、指令、循环变量、栈以及编译器额外访存不在采集范围内。因此这是<strong>源码层数组访问 Trace</strong>，并非真机完整指令 Trace 或硬件计数器测量。</p>
    <p>固定基址让实验可复现，也会影响冲突模式。尤其 4096 B 地址间隔和矩阵 512 B 行跨度都是本实验刻意保留的条件，结论不可脱离布局推广到所有程序。</p>""")
    h.append("<h2>4. 正确性与数据完整性</h2>")
    h.append("""<p>通过 16 项 unittest：覆盖地址分解、直接映射冲突、组相联容纳、LRU/FIFO 顺序、随机可复现、写分配、脏块换出、跨块访问、预热、解析、3C 手算、顺序访问理论命中率及相联度反例。
    其中一项用<strong>独立的时间戳与物理槽位实现</strong>，对 120 组随机配置逐项核对命中、失效、换出与脏块状态。主实现使用 OrderedDict 维护顺序，两者结构不同。</p>
    <p>每次实验检查 hits + misses = accesses，read_misses + write_misses = misses；LRU 再检查三类失效之和等于 misses。
    12 个 Trace 的 SHA-256 存在 manifest.json，运行前核对；参数、逐种子计数、统计汇总、环境与源码哈希全部保存。没有使用 Dinero IV 运行结果作为本实验数据。</p>""")
    h.append("<h2>5. 映射方式结果</h2>")
    h.append(image("01_mapping", "图 1｜每格为一条固定 Trace 的命中率，未对不同工作负载取总平均。"))
    h.append(table(["工作负载", "直接映射", "2 路", "4 路", "8 路", "全相联"],
                   [[labels[w]] + [f"{rate(w, ways=a):.3f}%" for a in [1, 2, 4, 8, 64]] for w in labels]))
    h.append("""<p><strong>组相联能消除特定映射冲突。</strong>两块间隔 4096 B 的地址反复交替时，直接映射命中率为 0%，2 路达到 99.994%（仅最初 2 次失效）。
    八块同组循环时，1/2/4 路 LRU 都为 0%，8 路为 99.976%（仅最初 8 次失效）。它说明瓶颈是每组可容纳的块数。</p>
    <p><strong>缺少可利用的局部性时，相联度收益很小。</strong>顺序扫描在所有映射下均为 93.75%，对应每个 64 B 块中 16 个 4 B 字的一次失效与十五次命中。
    均匀随机访问的命中率都在 6.1% 左右，与 4 KiB / 64 KiB 的 6.25% 容量比例接近。这里访问数有限，不能要求恰好等于该比例。</p>""")
    h.append("<h2>6. 替换策略结果</h2>")
    h.append(image("02_replacement", "图 2｜误差线仅描述固定 Trace 下 Random 替换种子的波动；很短的误差线可能在图中不易辨认。"))
    h.append(table(["工作负载（4 路）", "LRU", "FIFO", "Random 均值 ± 95% CI 半宽（百分点）"],
                   [[labels[w], f"{rate(w):.3f}%", f"{rate(w,policy='FIFO'):.3f}%",
                     f"{rate(w,policy='Random'):.3f}% ± {float(query(w,policy='Random')['ci95_half_pp']):.3f}"]
                    for w in labels]))
    h.append(f"""<p><strong>热点访问支持 LRU 的近期局部性假设。</strong>热点混合下 LRU 为 {rate('hot_cold'):.3f}%，FIFO 为 {rate('hot_cold',policy='FIFO'):.3f}%，
    相差 {rate('hot_cold')-rate('hot_cold',policy='FIFO'):.3f} 个百分点。LRU 在热点被重复访问时刷新位置，FIFO 仍可能按装入时间淘汰热点。</p>
    <p><strong>循环扫描能让 LRU 失去优势。</strong>五块争用四路时，循环次序为 A B C D E A B C D E……。
    LRU 刚好逐次淘汰下一个即将重用的块，所以命中率为 0%；FIFO 在该序列中也为 0%。
    Random 打破固定淘汰循环，均值为 {rate('cycle_5',policy='Random'):.3f}%。这不是 Random 普遍更优的证据，而是访问次序与替换规则相互作用的受控反例。</p>
    <p>统计方法：10 个独立替换种子，样本标准差 s，均值置信区间为 mean ± 2.262157 × s / √10（t 分布，9 自由度）。
    LRU/FIFO 是确定性结果，不通过重复同一输入制造统计样本。这里的区间不涵盖不同程序、Trace 生成种子或布局变化，因此不能解释为总体应用性能的置信区间。</p>""")
    h.append("<h2>7. 程序局部性实验</h2>")
    h.append(image("03_program_locality", "图 3｜只比较显式数组访问的命中率。两种转置实现的每轮数组读写次数相同。"))
    h.append(f"""<p>按行遍历命中率 {rate('row_scan'):.2f}%，按列遍历为 {rate('column_scan'):.2f}%。列遍历每次跨 512 B，访问同一缓存块的相邻元素前需要绕过整列，
    主配置既有同组竞争，工作集也超过 64 个缓存块；全相联 LRU 仍为 0%。</p>
    <p>朴素转置命中率 {rate('transpose_naive'):.3f}%，8×8 分块转置为 {rate('transpose_tiled'):.3f}%，提升
    {rate('transpose_tiled')-rate('transpose_naive'):.3f} 个百分点。分块把局部子矩阵的重用集中在较短时间内。
    块大小和矩阵布局会影响最佳 tile，本文只评估 tile=8，没有声称这是最优分块大小。</p>""")
    h.append("<h2>8. 容量、块大小与预热</h2>")
    h.append(image("04_capacity", "图 4｜横轴为 Cache 数据容量，固定 4 路与 64 B 块；并非固定组数。"))
    h.append("""<p>热点混合在 1 KiB 时为 26.634%，4 KiB 时为 86.096%，16 KiB 时为 92.127%，较大容量能容纳更多热点。
    但列遍历在扫描的 1–16 KiB、4 路配置中一直为 0%：128 个行块以块号步长 8 映射，在 16 KiB 的 64 个组中只使用 8 组，每组 16 个行块仍超过四路。
    因此这个结果不能解读为“增加容量对列遍历无效”，只能说明当前容量范围、相联度和固定行跨度下冲突仍未解除。</p>""")
    h.append(image("05_block_size", "图 5｜增大块会增加一次填充带来的相邻字，同时减少固定容量中的块数。"))
    h.append("""<p>顺序扫描从 16 B 块的 75% 上升到 128 B 块的 96.875%，符合 1 − 4/B。
    分块转置则从 64 B 块的 85.059% 降到 128 B 块的 80.664%，显示减少块数和改变组映射可抵消空间局部性收益。
    本实验没有模拟大块的传输延迟，不能据命中率直接选择最优块大小。</p>""")
    h.append(table(["工作负载", "策略", "冷启动完整 Trace", "剔除前 4096 次统计"],
                   [[labels[w], p, f"{rate(w,policy=p):.3f}%", f"{rate(w,experiment='warmup',policy=p):.3f}%"]
                    for w in ["hot_cold", "uniform_random", "cycle_5", "transpose_tiled"] for p in policies]))
    h.append("<p>两列分别统计完整 Trace 和相同 Trace 的后缀，分母不同。它是预热敏感性检查，不是严格稳态证明。热点下 LRU 优势和五块循环下 Random 优势在这项检查中均保留。</p>")
    h.append("<h2>9. 失效分类与相联度反例</h2>")
    h.append(image("06_miss_classes", "图 6｜分类只用于 LRU；对目标 Cache 的实际失效进行分类。"))
    h.append("""<p>判定方法：块第一次出现为首次访问失效；否则，若同容量全相联 LRU 的影子 Cache 也失效，记为容量类；若影子命中，记为冲突类。
    影子 Cache 对每次访问更新，包括目标 Cache 命中时。该定义是一种参照分类，不能把 FIFO/Random 与 LRU 的策略差异全部叫作映射冲突，因此其他策略不填 3C 数字。</p>
    <p>分类只在目标 Cache 实际失效时计数。目标 Cache 可能命中而影子 LRU 失效，所以跨配置的“容量类”计数不保证相等，
    也不能简单用“目标总失效 − 全相联 LRU 总失效”当作非负冲突次数。</p>""")
    h.append(image("07_counterexample", "图 7｜受控病态序列用于限定结论的适用范围，不能代表平均程序表现。"))
    h.append("""<p>循环读取 65 个连续块，而 Cache 只有 64 个块时，全相联 LRU 的复用距离超过容量，每次重访前块都已被淘汰，因此为 0%。
    直接映射仅让块 0 与块 64 争用同一个位置，其余 63 块受组隔离保护，命中率为 96.734%。
    这解释了为什么“更高相联度提供更多放置选择”并不等价于“给定在线替换算法在每条 Trace 上都更好”。全相联 LRU 也不能充当所有映射与替换策略的命中率上界。</p>""")
    h.append("<h2>10. 可用于汇报的结论与限制</h2>")
    h.append("""<ol><li>同组冲突明确时，增加路数可以大幅提高命中率，收益取决于竞争块数与组容量。</li>
    <li>热点重用场景中 LRU 表现更好；循环超额竞争中 Random 可优于 LRU/FIFO，策略选择依赖访问模式。</li>
    <li>调整程序访问顺序能显著提高缓存利用率。本次 8×8 转置分块带来 38.184 个百分点提升。</li>
    <li>容量、块大小、相联度共同影响结果。单一参数的经验趋势不能作为每条 Trace 都成立的定理。</li></ol>
    <p>适用范围：这些结论来自 8 条设计型 Trace 和 4 个简单数组内核，没有覆盖完整应用、真实物理地址、多级缓存、一致性、预取、乱序执行或真实替换硬件。
    精确 LRU 的硬件代价和相联查询延迟未建模。因此本实验比较的是数据访问命中率，<strong>没有测得真机运行加速比或硬件 AMAT</strong>。
    课件给出 AMAT = 命中时间 + 失效率 × 失效开销；本实验未测这两个时间参数，不填入假定数值冒充测量。</p>""")
    h.append("<h2>11. 复现与文件索引</h2>")
    h.append("""<p>在项目目录执行以下命令。核心仿真仅依赖 Python 标准库；重新生成程序 Trace 需要 C 编译器，绘图另需 matplotlib。</p>
    <pre>python3 -m unittest -v test_cache_sim
python3 run_experiments.py --regenerate
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python make_report.py
python3 audit_results.py

# 单个配置
python3 cache_sim.py traces/hot_cold.trace.gz --capacity 4096 --block-size 64 --ways 4 --policy LRU --classify</pre>""")
    h.append(table(["路径", "用途"],
                   [["cache_sim.py", "Cache 与命令行模拟器"],
                    ["generate_traces.py / kernels.c", "合成 Trace 与 C 数组插桩内核"],
                    ["test_cache_sim.py / audit_results.py", "正确性测试与结果完整性核对"],
                    ["run_experiments.py / make_report.py", "一键仿真与图表/报告生成"],
                    ["traces/*.trace.gz / manifest.json", "压缩 Trace、统计、来源与 SHA-256"],
                    ["results/raw_runs.csv", "768 次运行，逐种子原始计数"],
                    ["results/summary.csv", "300 组汇总，均值、标准差和 95% CI"],
                    ["results/parameters.json / run_metadata.json", "参数、环境、源码哈希"],
                    ["results/validation.txt / audit.json", "测试与结果核对记录"],
                    ["figures/*.png / *.svg", "7 张 PNG 及对应矢量图"],
                    ["results/ppt_key_results.csv", "后续 PPT 的主要数据表"]]))
    h.append("<h2>12. 后续 PPT 建议结构</h2>")
    h.append(table(["页", "主题", "建议素材"],
                   [["1", "实验问题与方法", "实验标题，研究对象和测量指标"],
                    ["2", "Cache 映射与替换原理", "地址分解公式、三种替换规则"],
                    ["3", "实验设计与可信度", "控制变量、12 条 Trace、16 项测试"],
                    ["4", "映射对比", "图 1，重点讲两块和八块冲突"],
                    ["5", "替换对比", "图 2，热点与五块循环两个对照"],
                    ["6", "程序局部性", "图 3，矩阵遍历与转置"],
                    ["7", "容量与块大小", "图 4、图 5，分两页也可"],
                    ["8", "3C 解释与反例", "图 6、图 7，突出条件而非绝对结论"],
                    ["9", "结论、局限与复现", "四条结论、文件清单、运行命令"]]))
    h.append("""<h2>参考资料</h2><p>[1] 用户提供的《第5章 存储层次.pptx》，课程本地文件，引用页码见第 1 节。<br>
    [2] Jan Edler、Mark D. Hill，<a href="https://pages.cs.wisc.edu/~markhill/DineroIV/">Dinero IV 官方说明</a>，
    访问日期 2026-11-07。用于核实 Trace 驱动模拟的范围：主要结果为 hit/miss，工具本身不模拟时间或数据功能。本文采用自写工具，不冒充 Dinero IV 实测。</p>""")
    h.append(f"<footer>运行完成时间（UTC）：{html.escape(metadata['completed_utc'])}。完整运行环境保存在 results/run_metadata.json。报告内图像已嵌入，可离线单独打开。</footer>")
    css = """body{margin:0;background:#f4f6f9;color:#203047;font:16px/1.85 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}
    main{max-width:1120px;margin:0 auto;background:white;padding:56px 64px}h1{font-size:38px;line-height:1.35;margin:10px 0 20px;color:#153959}
    h2{font-size:25px;line-height:1.5;margin-top:52px;padding-bottom:10px;border-bottom:2px solid #dce6ef;color:#153959}
    .eyebrow{font-weight:650;color:#1769aa;letter-spacing:2px}.lead{font-size:19px;color:#4c6073}.summary{padding:15px 0;border-block:1px solid #dce6ef;color:#1769aa;font-weight:600}
    p{margin:18px 0}.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;margin:18px 0 26px;font-size:14px;line-height:1.6}
    th,td{text-align:left;padding:12px 13px;border-bottom:1px solid #dae3ec;vertical-align:top}th{background:#eaf1f7;color:#153959;font-weight:650}
    tr:nth-child(even) td{background:#f8fafc}figure{margin:30px 0}img{width:100%;height:auto}figcaption{font-size:14px;color:#587086;margin-top:10px}
    code{background:#edf2f6;padding:2px 5px;border-radius:3px;font-size:14px}pre{white-space:pre-wrap;word-break:break-word;background:#edf2f6;padding:22px;font:14px/1.7 monospace}
    a{color:#1769aa}li{margin:12px 0}footer{border-top:1px solid #dce6ef;margin-top:45px;padding-top:20px;font-size:13px;color:#617383}
    @media(max-width:760px){main{padding:24px 18px}h1{font-size:29px}h2{font-size:22px}table{font-size:12px}}
    @media print{body{background:white}main{padding:0;max-width:none}h2{break-after:avoid}figure,table{break-inside:avoid}}"""
    document = "<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Cache 实验报告</title><style>" + css + "</style><main>" + "".join(h) + "</main></html>"
    (ROOT / "实验报告.html").write_text(document, encoding="utf-8")
    keys = ["experiment", "workload", "capacity_bytes", "block_bytes", "ways",
            "policy", "hit_rate_pct", "runs", "ci95_half_pp"]
    selected = [r for r in rows if r["experiment"] == "main"]
    with (ROOT / "results/ppt_key_results.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["中文名称"] + keys)
        writer.writeheader()
        for r in selected:
            writer.writerow({"中文名称": labels[r["workload"]], **{k: r[k] for k in keys}})
    print("Saved 7 PNG + 7 SVG figures, 实验报告.html and results/ppt_key_results.csv")


if __name__ == "__main__":
    charts()
    report()
