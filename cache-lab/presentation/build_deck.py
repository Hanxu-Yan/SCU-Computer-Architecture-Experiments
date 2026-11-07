from pathlib import Path
import csv
from native_pptx import Deck,ACCENT,GRAY,BROWN,MUTED

HERE=Path(__file__).resolve().parent
rows=list(csv.DictReader((HERE.parent/"results/summary.csv").open(encoding="utf-8-sig")))
def q(name,experiment="main",ways=4,policy="LRU",capacity=4096,block=64):
 found=[r for r in rows if r["workload"]==name and r["experiment"]==experiment and int(r["ways"])==ways and r["policy"]==policy and int(r["capacity_bytes"])==capacity and int(r["block_bytes"])==block]
 assert len(found)==1
 return found[0]
def val(name,**kw): return float(q(name,**kw)["hit_rate_pct"])/100
def bars(cats,values,colors=None,fmt="0.000%"):
 return dict(categories=cats,series=[dict(name="命中率",values=values,point_colors=colors or [ACCENT]*len(values))],format=fmt,labels=True)

d=Deck()
source="数据来源：cache-lab/results/summary.csv，与raw_runs.csv逐次记录对应。"
course="课程依据：《第5章 存储层次.pptx》。"
s=d.add(notes="这次实验比较Cache映射方式和替换策略对命中率的影响。采用自写Trace模拟器，让同一段访问序列在不同配置下运行，再从访问规律解释差异。")
s.text("计算机系统结构小组实验",66,96,1140,50,29,MUTED)
s.text("Cache 映射方式与替换策略\n对命中率的影响",64,228,1152,170,58,bold=True)
s.text("基于自写 Trace 模拟器",67,445,1050,54,32,ACCENT)
s.text("2026 年 11 月",67,605,1050,40,24,MUTED)

s=d.add("Cache 命中率为什么重要","Cache 缓解 CPU 与主存之间的速度差距",
 course+"第3、7、8页。平均访存时间等于命中时间加上失效率乘以失效开销，失效开销是未命中时额外付出的时间。这里用假设的单级访存参数说明：命中时间1 ns、失效开销50 ns，命中率95%时平均3.5 ns，98%时平均2.0 ns。这个算例说明，命中率的几个百分点可以明显改变平均访存时间。接下来关注在容量相同的条件下，映射与替换规则怎样影响命中率。")
s.text("数据命中 Cache 时可直接使用，失效时需要从下一级取回。",78,180,1120,48,29)
s.text("平均访存时间 = 命中时间 + 失效率 × 失效开销",78,255,1120,52,32,ACCENT)
s.text("假设命中时间为 1 ns，失效开销为 50 ns",78,335,1120,44,26,MUTED)
s.table([["命中率","失效率","平均访存时间"],
 ["95%","5%","1 + 5% × 50 = 3.5 ns"],
 ["98%","2%","1 + 2% × 50 = 2.0 ns"]],
 [270,270,612],[50,64,64],y=390,size=29)
s.text("容量相同时，映射与替换规则仍会改变命中率和访存开销。",78,610,1120,46,27)

s=d.add("映射与替换策略的应用场景","把程序中的访问特点，转成可比较的 Trace",
 course+"第12–27、50、54、60页讨论映射、替换及实现开销，第90、92页讨论循环交换和分块。处理器设计需要在命中表现与硬件开销之间取舍。矩阵计算可以通过访问顺序和分块改变局部性。热点数据夹杂大范围扫描时，冷数据会占用缓存位置，替换规则决定常用块能保留多久。最后一类访问用本实验的hot_cold序列抽象，定义见generate_traces.py及traces/manifest.json。主实验固定4 KiB容量和64 B块，比较不同映射与替换策略，再用访问模式解释结果。")
s.table([["应用场景","关注的问题","本实验的对应内容"],
 ["处理器 Cache 设计","容量有限时，减少同组冲突，\n同时考虑查找与替换开销。","比较不同映射方式\n和替换策略"],
 ["矩阵计算","按行或按列、是否分块，\n会改变相邻数据的复用。","按行 / 按列遍历\n朴素 / 分块转置"],
 ["热点数据与\n大范围扫描混合","常用块与冷数据争用空间，\n替换规则影响热点能否保留。","热点与冷数据混合\n比较 LRU / FIFO / Random"]],
 [256,500,396],[48,104,104,104],y=180,size=26)
s.text("我们在相同容量下比较映射与替换策略，\n再用不同访问序列解释命中率的差异。",78,582,1120,86,29,ACCENT)

s=d.add("映射方式决定块放在哪里","以主实验的 64 个缓存块为例",course+"第13–21页。每组有几块就是几路。主实验4096 B容量、64 B块，共64块。直接映射64组，每组1块；4路为16组；全相联为1组。")
s.table([["映射方式","Cache 如何分组","一个主存块可以放在哪里"],["直接映射","64 组，每组 1 块","固定的一个位置"],["4 路组相联","16 组，每组 4 块","固定组中的任意一路"],["全相联","1 组，共 64 块","Cache 中的任意位置"]],[240,340,572],[54,76,76,76],y=184,size=28)
s.text("组索引 = 块号 mod 组数",78,510,1120,50,32,ACCENT)
s.text("实验比较 1、2、4、8、64 路，数据容量始终保持相同。",78,577,1120,48,27)

s=d.add("替换策略决定组满后换掉谁",notes=course+"第25–27页。LRU按最近访问排序，命中也会更新；FIFO按装入时间排序，命中不更新。两路示例A B A C A：装入C时，LRU淘汰B，FIFO淘汰A，因此最后一次访问A出现差异。")
s.table([["策略","选择规则"],["LRU","淘汰最久没有被访问的块"],["FIFO","淘汰最早装入的块"],["Random","从组内已有块中随机选择一个"]],[220,932],[48,56,56,56],y=154,size=28)
s.text("两路 Cache，依次访问 A、B、A、C、A",78,406,1110,42,27)
s.table([["本次访问","A","B","A","C","A"],["LRU","失效","失效","命中","失效","命中"],["FIFO","失效","失效","命中","失效","失效"]],[220]+[186.4]*5,[48,54,54],y=463,size=26,numeric_from=1)

s=d.add("实验设置","同一条 Trace 在所有主实验配置中重复使用",source+"参数见results/parameters.json。记录均为对齐4 B访问，一次记录对应一次缓存块探测。模拟单级数据Cache。Random种子0–9，直接映射只有一路，运行一次即可。")
s.table([["参数","设置"],["容量与块大小","4 KiB，64 B，共 64 个缓存块"],["映射方式","直接映射，2 / 4 / 8 路组相联，全相联"],["替换策略","LRU、FIFO、Random"],["读写规则","写回、写分配，按需取块"],["初始状态","每次从空 Cache 开始，计入冷启动"],["随机重复","Random 使用 10 个替换种子"]],[245,907],[47]+[55]*6,y=176,size=27)
s.text("测量指标：单级数据 Cache 命中率 = 命中次数 / 访问次数",78,590,1120,48,27,ACCENT)

s=d.add("访问序列覆盖不同的局部性","12 条 Trace，共 768 次仿真",source+"Trace定义见generate_traces.py和traces/manifest.json。C程序实际编译运行，记录源码层显式数组访问。A、B逻辑基址为0x100000、0x200000，矩阵128×128 uint32，各内核运行4轮。16项测试包括120组配置与独立时间戳模型的核对。")
s.table([["类型","访问内容"],["空间与时间局部性","顺序扫描、小工作集复用、均匀随机"],["同组竞争","2 块、5 块、8 块同组循环"],["容量与热点","65 块循环、热点与冷数据混合"],["C 程序数组访问","按行 / 按列遍历、朴素 / 分块转置"]],[305,847],[48,64,64,64,64],y=177,size=27)
s.text("程序执行时记录数组读写，使用固定逻辑地址。",78,521,1120,43,27)
s.text("模拟器通过 16 项测试，含 120 组配置与独立实现的交叉核对。",78,583,1120,43,26,MUTED)

ways=[1,2,4,8,64]
s=d.add("增加路数可以解除同组冲突","4 KiB，64 B，LRU，命中率（%）",source+"main/conflict_2、conflict_8，ways=1,2,4,8,64。地址间隔4096 B，在这些配置下均映射到同组。两块循环32768次，2路后只有最初2次失效；八块循环32768次，8路后只有最初8次失效。")
s.chart(dict(categories=["直接映射","2 路","4 路","8 路","全相联"],series=[dict(name="2 块同组循环",values=[val("conflict_2",ways=a) for a in ways],color=ACCENT),dict(name="8 块同组循环",values=[val("conflict_8",ways=a) for a in ways],color=GRAY)],labels=False),h=425)
s.text("2 块循环",900,207,300,40,29,bold=True)
s.text("2 路起，命中率\n达到 99.994%",900,259,310,100,30,ACCENT)
s.text("8 块循环",900,408,300,40,29,bold=True)
s.text("8 路起，命中率\n达到 99.976%",900,460,310,100,30,ACCENT)
s.text("路数足以容纳竞争块后，后续访问都能命中。",80,620,1100,40,27)

s=d.add("热点访问中，LRU 更容易保留热点","4 KiB，64 B，4 路，命中率（%）",source+"main/hot_cold。LRU86.096%，FIFO78.725%，Random均值约78.761%，CI见summary.csv。LRU相对FIFO提升7.371个百分点。90%概率访问48个热点块，其余10%访问976个冷块，20%访问为写。")
s.chart(bars(["LRU","FIFO","Random"],[val("hot_cold",policy=p) for p in ["LRU","FIFO","Random"]],[ACCENT,GRAY,BROWN]))
s.text("90% 的访问\n落在 48 个热点块上",900,209,305,96,30,bold=True)
s.text("LRU 命中后更新次序，\n让常用块留得更久。",900,353,310,95,27)
s.text("FIFO 仍按装入时间\n选择被替换的块。",900,480,310,95,27)
s.text("LRU 比 FIFO 高 7.371 个百分点",80,616,900,43,29,ACCENT)

s=d.add("五块争用四路时，Random 命中率更高","4 KiB，64 B，4 路，命中率（%）",source+"main/cycle_5。LRU和FIFO为0，Random均值59.998291%，95%均值CI半宽约0.110个百分点。5个地址间隔4096 B，循环8192轮。LRU装入E时淘汰A，接着访问A淘汰B，形成每次失效的循环。")
s.chart(bars(["LRU","FIFO","Random"],[val("cycle_5",policy=p) for p in ["LRU","FIFO","Random"]],[ACCENT,GRAY,BROWN]))
s.text("访问顺序",900,208,300,40,29,bold=True)
s.text("A  B  C  D  E\nA  B  C  D  E",900,265,310,100,32,ACCENT)
s.text("LRU 刚淘汰的块，\n下一步又要访问。",900,409,310,95,27)
s.text("随机替换打破了\n固定的淘汰次序。",900,522,310,95,27)
s.text("Random：10 个种子的均值，95% 均值置信区间半宽为 0.110 个百分点",80,623,1100,42,23,MUTED)

s=d.add("按行遍历能连续使用同一个缓存块","128×128 矩阵，4 KiB，64 B，4 路 LRU，命中率（%）",source+"main/row_scan、column_scan。矩阵行主序，元素4 B，64 B块可放16个元素。按行命中率93.75%=15/16。列遍历步长512 B，同一块再次访问前要经过整列，基准配置中发生替换。")
s.chart({**bars(["按行遍历","按列遍历"],[val("row_scan"),val("column_scan")],[ACCENT,GRAY],fmt="0.00%"),"labels":False})
s.text("按行命中率 93.75%",900,210,312,90,28,bold=True)
s.text("一个 64 B 块可容纳\n16 个元素。首次失效，\n其余 15 次命中。",900,319,310,145,27)
s.text("按列命中率为 0%。\n每次跨 512 B，复用前\n要经历整列的访问。",900,490,312,115,27)
s.text("相同数据，访问顺序不同，命中率就会明显变化。",80,621,1100,40,27)

s=d.add("8×8 分块提高了矩阵转置的命中率","128×128 矩阵，4 KiB，64 B，4 路 LRU，命中率（%）",source+"main/transpose_naive、transpose_tiled。每次转置各读A和写B一次，均运行4轮、131072次数组访问。朴素46.875%，分块85.05859375%，提升38.18359375个百分点。内核见kernels.c，tile=8。")
s.chart(bars(["朴素转置","8×8 分块"],[val("transpose_naive"),val("transpose_tiled")],[GRAY,ACCENT]))
s.text("先完成一个小块，\n再处理下一个小块",900,213,310,100,31,bold=True)
s.text("需要重复使用的数据\n集中在较短时间内访问，\n更容易留在 Cache 中。",900,358,310,145,27)
s.text("两种实现的数组\n读写次数相同。",900,526,310,80,27)
s.text("命中率提升 38.184 个百分点",80,618,1100,42,29,ACCENT)

s=d.add("增大容量可以容纳更多热点","固定 64 B 块、4 路 LRU，命中率（%）",source+"capacity实验，容量1024、2048、4096、8192、16384 B。热点从26.634%依次提升到52.278%、86.096%、90.709%、92.127%。")
s.chart(dict(kind="line",categories=["1 KiB","2 KiB","4 KiB","8 KiB","16 KiB"],series=[dict(name=label,values=[val(w,experiment="capacity",capacity=c) for c in [1024,2048,4096,8192,16384]],color=color) for w,label,color in [("hot_cold","热点混合",ACCENT),("transpose_tiled","8×8 分块转置",BROWN),("uniform_random","均匀随机",GRAY)]],labels=False),x=64,y=175,w=1152,h=418)
s.text("热点访问在 1–4 KiB 区间提升较快，随后增幅放缓。",80,617,1110,44,28)

s=d.add("块大小的收益取决于访问方式","固定 4 KiB 容量、4 路 LRU，命中率（%）",source+"block_size实验。顺序扫描随16、32、64、128 B块得到75%、87.5%、93.75%、96.875%。分块转置分别73.33984375%、84.912109375%、85.05859375%、80.6640625%。固定容量时块增大，总块数和组数减少。")
s.chart(dict(kind="line",categories=["16 B","32 B","64 B","128 B"],series=[dict(name=label,values=[val(w,experiment="block_size",block=b) for b in [16,32,64,128]],color=color) for w,label,color in [("sequential","顺序扫描",ACCENT),("transpose_tiled","8×8 分块转置",BROWN)]],labels=False),x=64,y=175,w=1152,h=418)
s.text("大块有利于顺序读取相邻元素，也会减少可保存的缓存块数。",80,617,1110,44,27)

s=d.add("65 块循环中，直接映射保住了 63 个块","64 个缓存块，65 块循环访问，LRU，命中率（%）",source+"main/capacity_cycle。65个连续块循环512轮。直接映射仅块0和块64争用同一位置，其余63块首次装入后持续命中，命中率63×511/(65×512)=96.733774%。全相联LRU重用一个块前已访问64个其他块，故每次失效。")
s.chart({**bars(["直接映射","2 路","4 路","8 路","全相联"],[val("capacity_cycle",ways=a) for a in ways],[ACCENT,GRAY,GRAY,GRAY,BROWN],fmt="0.00%"),"labels":False})
s.text("直接映射：96.734%",900,208,310,45,30,bold=True)
s.text("只有两个块争用一格，\n其余 63 块留在原位。",900,268,310,115,27)
s.text("全相联 LRU：0%",900,426,310,45,30,bold=True)
s.text("一个块再次被访问前，\n已被循环次序淘汰。",900,487,310,115,27)
s.text("映射的分组方式，会改变替换策略对访问序列的响应。",80,622,1100,42,27)

s=d.add("实验结论",notes="选型依据落在访问模式：同组竞争先看路数是否够用，热点重用适合LRU，固定循环中Random可能占优，程序本身也能通过分块改善局部性。容量、块大小与映射关系一起考虑。"+source)
for y,heading,t in [(172,"同组冲突","路数达到竞争块数后，循环访问可以持续命中。"),(282,"热点重用","LRU 刷新近期访问次序，保留热点的效果更好。"),(392,"固定循环","替换次序可能与访问次序冲突，Random 能打破循环。"),(502,"程序局部性","调整访问顺序与分块，可以显著提高命中率。")]:
 s.text(heading,79,y,235,50,31,ACCENT,True)
 s.text(t,328,y+2,875,84,29)

s=d.add("附录：映射方式的完整结果","4 KiB，64 B，LRU，命中率（%）",source+"main的12条Trace和5种相联度，显示3位小数。CSV保留更高精度。")
labels={"sequential":"顺序扫描","small_reuse":"小工作集复用","conflict_2":"2 块同组循环","conflict_8":"8 块同组循环","cycle_5":"5 块同组循环","capacity_cycle":"65 块循环","hot_cold":"热点混合","uniform_random":"均匀随机","row_scan":"按行遍历","column_scan":"按列遍历","transpose_naive":"朴素转置","transpose_tiled":"8×8 分块转置"}
data=[["访问序列","直接映射","2 路","4 路","8 路","全相联"]]+[[label]+[f"{val(w,ways=a)*100:.3f}" for a in ways] for w,label in labels.items()]
s.table(data,[302]+[170]*5,[39]+[37]*12,y=172,size=23,numeric_from=1)

s=d.add("附录：结果验证与复现",notes=source+"验证记录results/validation.txt、audit.json。输入traces/*.trace.gz；参数results/parameters.json；源码cache_sim.py、kernels.c。课程参考《第5章 存储层次》13–27、29–31、49–60页。")
s.text("正确性检查",78,168,1080,50,31,bold=True)
s.text("16 项测试，覆盖命中、替换、写回、跨块访问和预热。\n其中 120 组配置与独立的时间戳实现逐项核对。",78,228,1100,105,28)
s.text("复现实验",78,376,1080,50,31,bold=True)
s.text("python3 run_experiments.py --regenerate",78,442,1110,50,28,ACCENT)
s.text("原始记录：results/raw_runs.csv\n汇总数据：results/summary.csv",78,519,1100,88,26)
s.text("课程参考：《第5章 存储层次》，映射与替换、失效类型及优化部分",78,626,1120,35,22,MUTED)

assert len(d.slides)==18 and len(d.charts)==8
d.save(HERE/"build/candidate.pptx")
