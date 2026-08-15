# exebox 需求文档

> 版本:v1 草案(2026-08-15)· 状态:待评审
> 本文档讲 **Why 与 What**;How 见 [exebox-design.md](exebox-design.md),
> 竞品与生态位论证见 [research-alternatives.md](research-alternatives.md)。
> 需求依据:2026-08-15 三场实战(PvZ/RA2/MO3 攻坚)+ Lutris/umu 源码逆向 + 社区调研。

---

## 1. 产品愿景

**一句话**:wine/proton 的前端 —— 快速方便地在 Linux 上玩转 exe 程序,
把 Windows 软件迁移到 Linux 平台。

**定位宣言**:我们不做又一个游戏启动器。我们做的是 Windows 软件在 Linux 上的
**搬运与管理层**:一个程序的全部运行时需求(引擎版本、假电脑、入口、环境、
安装步骤)写成一份可读、可 git、可分享的清单,一条命令启动,一条命令清除。

**核心张力与立场**:易用性 ↔ 专业性/灵活性/底层能力充分暴露,二者矛盾,
**尽可能都要**:

- 易用侧承诺:8 步向导产出清单、一张表看清全部家当、`launch <slug>` 开玩、
  出错时说人话
- 专业侧承诺:每次启动的完整命令行与环境可审计、清单即代码可 diff、
  Proton/prefix/进程树的每个旋钮都是显式字段、清单之外**零行为**

**口号候选**:"Wine prefix as code" / "一个目录,一个 Windows 程序"。

---

## 2. 问题陈述(现状为何不可忍)

源自实战与调研(research-alternatives.md §一):

| # | 痛点 | 实证 |
|---|---|---|
| P1 | 启动器在背后改命令行 | GE-Proton protonfixes 按 ID 偷塞 `-changedir`,PvZ 直接报 invalid arguments |
| P2 | 配置不可见、不可迁移 | Bottles 配置锁 GUI 内部;Lutris YAML 是内部格式;prefix 是黑盒快照 |
| P3 | 程序残留删不干净 | config/prefix/日志/桌面项分散四处,卸载靠考古 |
| P4 | 进程"启动即放手" | 游戏崩溃后幽灵锁卡死下次启动;孤儿进程满地;杀错 wineserver 误伤邻居 |
| P5 | 非游戏软件被忽视 | Heroic 限定游戏商店;Lutris"生产力版"issue 无下文 |
| P6 | CLI 是二等公民 | 自动化/远程/CI 场景无解;Reddit 呼吁"wine 界的 nvm"多年无人接 |
| P7 | 弹窗式交互 | Lutris 的嵌套设置对话框;配置过程不可回顾、不可 diff |

---

## 3. 目标用户

| 画像 | 描述 | 核心诉求 | 优先级 |
|---|---|---|---|
| **U1 迁移者** | 想在 Linux 上继续用某个 Windows 软件(办公/工具/老游戏)的普通用户 | "帮我把这个 exe 弄能跑,别让我懂 wine" | v1 主力 |
| **U2 玩家** | 老游戏/mod 玩家,愿意调参 | DLL 覆盖、渲染器、PATH 注入、dry-run 审计 | v1 主力 |
| **U3 工程师** | 用脚本/CI/SSH 管理 Windows 程序的开发者 | 纯 CLI、可复现清单、进程树治理、退出码可靠 | v1.x |
| U4 管理员 | 批量部署 Windows 软件到 Linux 机群 | 清单分发 + 声明式安装 | v2 观察 |

U1 与 U2 的张力即 §1 的核心张力:U1 要向导和默认值,U2 要全部旋钮 —— 
解法是"向导生成清单 + 清单全字段暴露",两类用户各取所需。

---

## 4. 核心用户故事(全部来自实战)

| # | 故事 | 战役来源 |
|---|---|---|
| US-1 | 作为 U1,我给安装器 exe,向导问几个问题,之后一条命令运行程序 | PvZ 安装器场景 |
| US-2 | 作为 U2,我在清单里写死 DLL 覆盖和 PATH 注入,每次启动稳定复现 | MO3 的 ddraw=n,b + mono 路径解析 |
| US-3 | 作为 U2,我启动前先看"到底会执行什么命令、带什么环境",确认无隐藏行为 | --changedir 血案后的信任重建 |
| US-4 | 作为 U1,程序坏了我不慌:删掉它的箱目录重新 install,一切重来 | MO3 三个阵亡 wine prefix 的教训 |
| US-5 | 作为 U3,游戏崩了不留幽灵:Ctrl-C/kill 干净收割整棵进程树,退出码可靠 | wineserver 幽灵锁 + 误杀 PvZ 惨案 |
| US-6 | 作为 U2,我换 Proton 版本前被明确警告 prefix 升级不可逆 | 版本棘轮(docs/proton-structure.md) |
| US-7 | 作为 U1,出错时我看到人话诊断和日志路径,不是 traceback | 全程实战的调试体验 |
| US-8 | 作为 U3,我把清单提交 git,换机器 clone 后 apply 即复现 | "prefix 黑盒"痛点(P2) |

---

## 5. 功能需求

优先级:【M】v1 必须 ·【S】v1.x 应该 ·【C】v2 可以 ·【W】不做(见 §7)

### 清单与数据模型

- **FR-1【M】** 一个程序 = 一个箱目录:manifest + prefix + 日志同处一箱;
  目录名即程序 ID;删除箱目录 = 彻底卸载(US-4)
- **FR-2【M】** 声明式 YAML 清单是**唯一配置真相**:引擎/prefix/入口/cwd/
  env/DLL 覆盖/args/PATH 注入/安装步骤全字段化(US-2, US-8)
- **FR-3【M】** 清单可引用箱外路径(复用现存 prefix 与游戏文件,
  如 Steam compatdata)(RA2 共存场景)
- **FR-4【S】** 清单 schema 版本字段,向前兼容策略明确

### 命令面

- **FR-5【M】** `list`:一张扁平紧凑表格,全部参数可见;`--all` 附健康检查
  (prefix 存在/版本匹配/exe 存在);`--protons` 列本机可用引擎(反 P7)
- **FR-6【M】** `launch <slug>`:按清单启动;`--dry-run` 打印完整命令行+环境
  (US-3);`--env` 临时覆盖
- **FR-7【M】** `install`:交互向导(默认值开路,专家可改每一步)+
  非交互模式(`--manifest`/`--import`)(US-1)
- **FR-8【M】** 安装步骤原语:shell(经同一引擎跑)/reg_add/copy/mkdir,
  顺序执行、失败即停(US-1;MO3 注册表修复即 reg_add 实例)
- **FR-9【S】** `launch --bg` 后台模式 + `ps` 查看运行中程序(US-5 延伸)
- **FR-10【S】** `doctor <slug>`:体检并给出修复建议(诊断手册产品化)

### 引擎与假电脑(prefix)管理

- **FR-11【M】** Proton 发现:扫本机已装(官方 + compatibilitytools.d),
  按名称/模糊名解析;**不自动下载**(把决定权留给用户)
- **FR-12【M】** prefix 脚手架:自动创建合规目录结构(含锁文件预建)
- **FR-13【M】** 版本棘轮防护:启动前比对 prefix 版本与引擎版本,
  托管型(Steam compatdata)版本不符拒启,自建型需显式确认(US-6)
- **FR-14【M】** 托管 prefix 只读策略:绝不写 Steam 管理的箱
- **FR-15【S】** prefix 生命周期:`reset`(清空重建)/`shell`(进箱内终端,
  类 docker exec)

### 进程治理

- **FR-16【M】** 启动即接管:新会话 + 子收割者(subreaper)+ 信号全树转发
  (US-5,生态零实现的空白)
- **FR-17【M】** 可靠退出码:游戏退出/被杀/超时,CLI 如实报告
- **FR-18【S】** 永不误伤:信号只打自己进程树,文档明示 wineserver 红线

### 日志与可观测

- **FR-19【M】** 每次启动落一份日志(箱内 logs/),启动摘要含日志路径(US-7)
- **FR-20【M】** 清单外零隐藏行为:无按 ID 注入、无参数重写、无环境暗改(US-3)

---

## 6. 非功能需求

| # | 需求 | 度量/验收 |
|---|---|---|
| NFR-1 | **可审计性** | 任意启动可用 --dry-run 完整复现;清单外字段数 = 0 |
| NFR-2 | **可版本化** | 清单纯文本,git diff 友好;箱内无派生状态混入 manifest |
| NFR-3 | **依赖最小** | 运行时依赖 ≤3(pyyaml/rich/typer);无守护进程;无联网 |
| NFR-4 | **性能** | list/dry-run 秒级(<300ms 感知);launch 开销仅剩 proton 自身 |
| NFR-5 | **健壮性** | 所有失败路径输出人话(错误码+建议动作),不露 traceback |
| NFR-6 | **可测试性** | core 纯库:构建环境/命令/校验均无副作用可单测;GUI 可复用 |
| NFR-7 | **文档一致性** | 行为规范与 docs/proton-*.md 实证文档互引,不出现无据行为 |
| NFR-8 | **安全边界** | 禁 shell=True;路径全 Path 化;不提权;不动清单外文件 |

---

## 7. 负面需求(Won't)

| 不做 | 理由 |
|---|---|
| 扫描/导入 Steam/Epic/GOG 库 | 不偷摸别人的库 |
| 管理 Linux 原生应用 | exe 之外不管 |
| 内置游戏数据库/在线脚本仓/自动 protonfixes | 零隐藏参数支柱;修复知识放清单里由用户掌控 |
| 自动下载引擎/组件 | 不替用户做网络与版本决定 |
| GUI(v1) | 清单即 UI;CLI 先行(core 已 GUI-ready) |
| 虚拟机/容器路线 | 我们是 wine/proton 前端,不做 hypervisor |

---

## 8. 成功标准(验收)

**v1 铁三角(全部为真实存量,开箱可测)**:

1. `exebox launch pvz` → 植物大战僵尸可玩,清单 ≤10 行
2. `exebox launch ra2` → 尤里复仇可玩,复用 Steam prefix 且零写入
3. `exebox launch mo3` → 心灵终结全链启动(客户端→Syringe→gamemd),
   DLL 覆盖与 PATH 注入来自清单,`--dry-run` 可审计

**v1.x 加冕**:用一个**非游戏** Windows 程序(待选:某工具类 exe)走完
install→launch→reset 全流程,验证"迁移者"画像成立(US-1 端到端)。

**北极星指标(定性)**:用户可以看着 `--dry-run` 的输出,向别人解释清楚
"这个程序是怎么跑起来的" —— 这就是专业性 + 易用性同时成立的那一刻。

---

## 9. 开放问题

1. 命名定稿(影响包名/环境变量/目录;exebox 为占位)
2. v1.x 的 `ps`/`doctor` 是否提前(取决于真实使用频率)
3. 非游戏验收程序选型(需要找一个有代表性、可自由分发的 Windows 工具)
4. GUI 技术选型(textual vs PySide)—— v1 结束后议

---

## 10. 文档关系

```
requirements.md   ← 本文档:Why / What(需求与愿景)
exebox-design.md  ← How:清单 schema、模块架构、行为规范、里程碑
research-alternatives.md ← 生态位论证:空白矩阵、竞品对照
proton-*.md / process-tree.md ← 底层实证:行为规范的事实依据
```
