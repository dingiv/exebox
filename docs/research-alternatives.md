# 竞品调研:这个轮子是否必要再造?

> 2026-08-15,两路并行调研(成熟工具全景 + 精确生态位挖掘)交叉验证。
> 结论先行:**有必要造,且生态位真实存在**。依据见下。

---

## 一、成熟工具全景(2025-2026 现状)

| 工具 | 配置模型 | CLI | Proton | 维护 | 核心问题(与我们目标对照) |
|---|---|---|---|---|---|
| **Lutris** (8.7k★) | per-game YAML 但是**内部格式** | 二等公民 | umu+GE | 活跃 | GUI 优先;游戏向;依赖按 ID 注入修复;UI 老旧被社区持续抱怨 |
| **Bottles** (10.2k★) | bottle.json **不可手写** | **无** | UMU+ProtoSoda | 极活跃 | 纯 GUI;Flatpak 沙箱限制底层灵活性;"Lutris 功能缩水版"之讥 |
| **Heroic** (12k★) | 内部 JSON | 部分 | GE+UMU | 极活跃 | **限定游戏商店**,不能跑任意 exe |
| **CrossOver** ($74/年) | GUI 数据库 | 无 | 自家 Wine | 活跃(就是 Proton 开发商) | 商业订阅;Linux 上免费 Proton 更强,价值存疑 |
| **PlayOnLinux/Phoenicis** | 脚本驱动 | 有限 | 无 | **半废弃** | PoL5 永远 Alpha |
| **Q4Wine** (731★) | GUI 数据库 | 无 | 无 | 维护模式 | 纯 Wine、UI 古老 |
| **WineZGUI** (133★) | Bash 变量 | 可用 | 无 | 低活跃 | Zenity 对话框,无 Proton |
| **winetricks** (3.5k★) | 环境变量+参数 | 纯 CLI | 无直接 | 年更 | 无 prefix 生命周期管理,是辅助工具不是前端 |
| **ProtonPlus** (1.7k★) | 无 | 无 | 仅版本管理 | 活跃 | 只管 runner 下载,不跑程序 |

**五大共同空白**(两路调研一致确认):

1. **没有 CLI 优先 + 声明式配置的通用 wine/proton 管理器**
   (Reddit 有人明确呼吁"wine 界的 nvm",至今无人满足)
2. 非 Steam 的 Proton 使用体验碎片化,缺统一抽象
3. **生产力软件/非游戏场景被系统性忽视**(Lutris 有"做个生产力版吧"的 issue,无下文)
4. 可复现性缺失:prefix 是黑盒快照,无法 diff/git/声明式重建
5. 开发者/自动化接口匮乏:没有库 API,无法进 CI/Makefile

## 二、精确生态位挖掘(按重合度)

| 候选 | 重合度 | 活跃度 | 关键差异 |
|---|---|---|---|
| **proton-caller**(Rust CLI 直调 Proton) | 中 | 11★,停滞 | 全局唯一 conf,无 per-app 清单、无 env/DLL、无进程管理 |
| **nihil5320/proton-launcher**(Go,per-game TOML) | 中低 | 1★ | 最接近"声明式"念头,但无箱结构/无步骤/无治理,太小 |
| protontools / proton-cli | 低 | 2★ 级 | 玩具级 |
| **umu-launcher** (3.6k★) | 后端非竞品 | 活跃 | 自我定位"被集成的运行层",**明确不做管理面** —— 正是我们上面那层 |
| **Nix wrapWine/mkwindowsapp** | 理念最像 | 社区实验 | 锁死 Nix DSL,普通用户无缘 |
| docker-wine | 路径不同 | 个人模板 | 容器路线,非原生 Proton |
| deep-wine-runner(deepin) | 低 | 绑发行版 | Qt GUI + deb 打包,deepin/UOS 专用 |

## 三、空白矩阵

| 我们的特征 | 现有最佳近似 | 空白? |
|---|---|---|
| 声明式 YAML 清单(用户合约) | Lutris YAML(内部格式)/Nix(DSL 锁定) | ✅ |
| 一程序一箱(manifest+prefix+日志同目录) | 全员分散存储(config/prefix/日志三处) | ✅ |
| CLI 优先 + 零隐藏参数 | proton-caller 太简陋;Lutris CLI 二等 | ✅ |
| 自管理进程树(subreaper/信号树) | **零实现**(全部"启动即放手") | ✅ |
| 通用 Windows 软件(非游戏向) | Bottles 支持但 GUI only;deepin 绑发行版 | ✅ |
| 拒绝按 ID 偷注入 | Lutris/umu-database 仍依赖查表注入 | ✅ |

## 四、结论:轮子必要,差异化六条

1. **"Wine prefix as code" 首次落地**:清单是用户合约而非内部格式 —— 可读、可 git、可分享、可 diff
2. CLI 优先 + 零隐藏参数,生态中独一无二
3. **箱模型**:`rm -rf` 一个目录即彻底清除一个程序(现有工具删不干净),可复现性质变
4. 自管理进程树填真实空白 —— 服务器/自动化/CI 跑 Windows 软件的刚需,目前零满足
5. 非游戏向天然避开 Lutris/Heroic/Bottles 主战场,瞄准没人认真做的迁移场景
6. 底层不重复造:umu 已把"半个 Steam"标准化,我们站在它上面做管理面
   (注:本设计选择自研薄层直调 proton 以零依赖,umu 作为备选后端保留)

### 风险与借鉴

- **风险**:Bottles/Lutris 若哪天补上 CLI+声明式,先发优势消失 → 靠"非游戏向 +
  零隐藏参数"的口碑差异;生态位小众(个人工具属性强)
- **从 Lutris 借鉴**:其 YAML installer 的 steps 语法(installer/task 动词体系)
- **从 Bottles 借鉴**:bottle 一站式目录的运营经验、runner 版本管理 UI(二期 GUI)
- **从 umu 借鉴**:已逆向完毕的三件套(脚手架/env/subreaper),源码级移植
- **从 proton-caller 借鉴**:极简 CLI 的克制(它是好的下限样本)

## 五、主要来源

- Lutris/Bottles/Heroic/winetricks/ProtonPlus 的 GitHub 仓库与 issue
- r/linux_gaming:"Lutris kinda sucks"、"command line wine version manager" 等讨论
- lutris#2963(生产力版需求无下文)
- proton-caller、nihil5320/proton-launcher、protontools README
- NixOS nixpkgs wine 打包讨论、deepin 社区
