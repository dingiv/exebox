# exebox 设计文档

> 状态:**草案 v1**(2026-08-15),实现未启动。
> 命名 exebox 为占位符,定稿前可改。
> 依据:本目录四份 Proton 实证文档 + umu-launcher 1.4.4 / Lutris 0.5.22 源码逆向。
> 行号引用均指 `~/Documents/codes/games/src/` 下对应源码。

---

## 1. 使命与范围

**本质:wine/proton 的前端。** 瞄准"快速方便地在 Linux 上玩转 exe 程序,
把 Windows 软件迁移到 Linux 平台"。

**只做三件事:安装 exe、管理 exe、启动 exe。**

一个程序 = 一个"箱"(manifest + prefix + 日志),箱即目录,目录名即 ID。

### 产品张力与取舍(2026-08-15 用户定调)

易用性 ↔ 专业性/灵活性/底层引擎能力的充分暴露,二者矛盾,**尽可能都要**:

- 易用侧:`install` 向导 8 步出清单、`list` 一屏看清、`launch <slug>` 一键开玩
- 专业侧:环境组装全过程可审计(`--dry-run` 全量打印)、清单即代码可 diff 可版本化、
  Proton/prefix/进程树的每个旋钮都暴露为显式字段、不设任何清单外的隐藏行为

### 负面清单(明确不做)

| 不做 | 理由 |
|---|---|
| 扫描/导入 Steam 库、Epic、GOG | 偷摸别人库是 Lutris 的病,不是我们的 |
| 管理 Linux 原生应用 | exe 之外的事一概不管 |
| 内置游戏数据库/在线脚本仓 | 清单由用户手写或向导生成,工具不联网 |
| protonfixes 式按游戏 ID 注入修复 | 零隐藏参数支柱(见 §2.1),--changedir 血案 |
| GUI 配置界面(v1) | 配置就是 game.yaml 本身,编辑器即 UI |
| 自动下载 Proton | 只发现本机已装的,不替用户做决定 |

---

## 2. 三根设计支柱

### 2.1 零隐藏参数

清单之外,一个字节都不加。具体承诺:

- 直调官方 Proton(`steamapps/common/Proton - Experimental/`),**无 protonfixes 层**
  —— GE-Proton 的 protonfixes 会按游戏 ID 偷偷追加参数(实证:
  `proton-ge/GE-Proton11-3/protonfixes/gamefixes-steam/3590.py:48` 对 PvZ 追加
  `-changedir`,非 Steam 版直接报 invalid arguments)
- 绝不经 `wine start`/`msiexec` 间接启动重写命令行(Lutris `get_real_executable`
  对 .lnk 走 start,是 --changedir 双横线形态的来源)
- cwd 用 `Popen(cwd=…)` 传递,**绝不**转成命令行参数
- `launch --dry-run` 打印最终命令行与环境全量,可审计

### 2.2 自研薄层

不依赖 umu/Lutris 任何运行时二进制。直调 Proton 脚本,只复刻 umu 三件不可或缺的
能力(源码级参考 `umu-launcher/umu/umu_run.py`):

| 能力 | umu 出处 | 说明 |
|---|---|---|
| compatdata 脚手架 | setup_pfx, L79-121 | pfx 自指链接、shadercache、steamuser 舞蹈 |
| 环境组装 | L209-327 | 取最小集,见 §6.1 |
| subreaper + 信号树 | L693-747 | PR_SET_CHILD_SUBREAPER + /proc 树遍历收割 |

### 2.3 core 即库

- 全部 API 返回 dataclass 或抛 `ExeboxError` 子类
- `exebox.core` 内**禁止** print / sys.exit / os._exit —— 那是 CLI 层的事
- v1 CLI(typer)与二期 GUI(textual 或 PySide,见 §11)消费同一 core
- 纯逻辑(可单测、GUI 可调)与副作用(进程/文件系统)按 §5.2 表严格分界

---

## 3. 清单格式规范(game.yaml)

compose 风格:整体是声明式快照,仅 `install.steps` 是安装期的顺序步骤。
运行时清单只读,无"构建"阶段。

### 3.1 Schema

| 字段 | 类型 | 默认 | 语义 |
|---|---|---|---|
| `name` | str | 目录名 | 人类可读名,list 显示用 |
| `exe` | str | **必填** | exe 路径;相对则基于 `game_dir` |
| `proton` | str | `"Proton - Experimental"` | Proton 名称,解析顺序见 §5.1 |
| `prefix` | str | `<箱>/prefix` | compatdata 根目录,可绝对路径外置复用 |
| `game_dir` | str | exe 所在目录 | **启动 cwd,绝不猜测**(相对则基于箱根) |
| `env` | map | {} | 追加环境变量,最高优先级覆盖 |
| `dll_overrides` | str | — | `env.WINEDLLOVERRIDES` 便捷别名,如 `"ddraw=n,b"` |
| `args` | [str] | [] | 原样追加到 exe 命令行 |
| `game_id` | int | 0 | **0 = 完全不设 SteamAppId**(实证:不设照样跑);非零才注入 SteamAppId/SteamGameId |
| `path_append` | [str] | [] | 启动时前插 PATH 的目录(mono Process.Start 场景) |
| `verb` | str | `run` | proton verb;实证 `run` 阻塞至游戏退出 |
| `notes` | str | "" | 给人看的备注 |
| `install.source` | str | — | 安装器 exe 路径 |
| `install.steps` | [step] | [] | 安装期步骤,见 §7.3 |

### 3.2 三个真实样例(v1 验收标准)

```yaml
# ~/Games/exebox/pvz/game.yaml —— 直调 proton、复用现役 prefix
name: Plants vs Zombies
exe: ./PlantsVsZombies.exe
proton: Proton - Experimental
prefix: /home/div/Documents/codes/games/pvz-exp-prefix
game_dir: /home/div/Documents/codes/games/pvz/Plants_Vs_Zombies_V1.0.0.1051_EN
notes: PopCap 引擎要求 cwd=游戏目录(相对路径找 main.pak);prefix 为直调风格(无 shadercache)
```

```yaml
# ~/Games/exebox/ra2/game.yaml —— Steam 托管 prefix,只读策略
name: "C&C: Red Alert 2 - Yuri's Revenge"
exe: ./gamemd.exe
prefix: /home/div/.local/share/Steam/steamapps/compatdata/2229850
game_dir: /home/div/.local/share/Steam/steamapps/common/Command & Conquer Red Alert II
notes: 路径含空格,全链 list 传参禁 shell=True;原版 RA2 把 exe 换 game.exe
```

```yaml
# ~/Games/exebox/mo3/game.yaml —— umu 风格 prefix + PATH 注入 + DLL 覆盖
name: Mental Omega 3
exe: ./MentalOmegaClient.exe
prefix: /home/div/Games/mo3
game_dir: /home/div/Games/mo3/drive_c/Program Files (x86)/Mental Omega
dll_overrides: "ddraw=n,b"
path_append:
  - /home/div/Games/mo3/drive_c/Program Files (x86)/Mental Omega
notes: 启动链 client→clientdx→Syringe→gamemd;mono 靠 PATH 解析相对名;
  prefix 的 pfx 是自指符号链接,两种布局都要认
```

---

## 4. 目录布局

```
~/Games/exebox/                        # 库根(EXEBOX_HOME 可覆盖)
├── registry.json                      # 纯缓存:index 加速,可 rescan 重建
└── <slug>/                            # 一箱一游戏,目录名 = 稳定 ID
    ├── game.yaml                      # 唯一真相
    ├── prefix/                        # 默认 prefix 位(manifest 可外置)
    │   ├── pfx -> .                   #   umu 风格自指链接(或真目录,见 §6.4)
    │   ├── pfx.lock / tracked_files / version / shadercache/ / gstreamer-1.0/
    └── logs/
        └── 2026-08-15T10-30-00.launch.log
```

设计要点:

- **slug 即 ID**:无 UUID、无数字主键,`exebox launch mo3` 直接映射到
  `~/Games/exebox/mo3/game.yaml`,人类可导航、git 友好
- **游戏文件不必入箱**:`exe`/`game_dir`/`prefix` 均可绝对路径指向箱外
  (RA2 的游戏文件永远在 steamapps 里,箱里只有清单)
- **registry.json 是缓存不是真相**:损坏后 `list --rescan` 扫 `*/game.yaml` 重建

### 与现存三游戏的共存策略

| 游戏 | prefix 归属 | 策略 |
|---|---|---|
| pvz | 自建(直调风格,无 shadercache) | 外置引用;scaffold 只补缺不动有 |
| ra2 | Steam compatdata | 托管检测(见 §6.5)→ 只读:版本不符拒启、不写 tracked_files |
| mo3 | umu 风格(pfx 自指链接) | 外置引用;布局检测兼容两种 |

---

## 5. core 模块划分

### 5.1 包结构与职责

```
exebox/
├── models.py            # dataclass:GameManifest/ProtonVersion/LaunchResult/GameEntry/InstallStep…
├── errors.py            # 异常层级:ExeboxError → Manifest/Proton/Prefix/Launch/Install/Registry
├── config.py            # LIBRARY_ROOT/PROTON_HOME(EXEBOX_* 环境变量覆盖)
├── manifest/loader.py   # YAML 解析+校验+路径解析(相对→绝对,基于箱根)
├── proton/resolver.py   # Proton 发现与名称解析
├── proton/runner.py     # build_environment/build_command(纯)+ execute(副作用)
├── prefix/manager.py    # scaffold/版本棘轮检查/托管检测
├── launch/process.py    # subreaper + /proc 树遍历 + 信号转发
├── launch/launcher.py   # launch 编排 + dry_run
├── install/installer.py # install 编排
├── install/steps.py     # step 执行器:shell/reg_add/copy/mkdir
├── registry/store.py    # registry.json CRUD + rescan
└── cli.py               # typer 入口(唯一允许 print 的层)
```

**ProtonResolver 名称解析顺序**(manifest 的 `proton` 字段):
1. `~/.local/share/Steam/compatibilitytools.d/<名称>/proton` 存在
2. `~/.local/share/Steam/steamapps/common/<名称>/proton` 存在
3. 模糊匹配(去空格小写):`proton-experimental` ≈ `Proton - Experimental`
4. 校验 `proton` 脚本存在且可执行;读取 `version` 文件供棘轮比对

### 5.2 纯逻辑 / 副作用分界(GUI 就绪的核心约束)

| 模块 | 纯逻辑 | 副作用 |
|---|---|---|
| ManifestLoader.load | ✓ | — |
| ProtonResolver.list/resolve | ✓(只读) | — |
| PrefixManager.check_version / is_managed | ✓(只读) | — |
| ProtonRunner.build_environment / build_command | ✓ | — |
| Launcher.dry_run | ✓ | — |
| PrefixManager.scaffold | — | mkdir/symlink |
| ProtonRunner.execute | — | 进程/prctl/信号 |
| ProcessManager.* | — | prctl/kill//proc 读 |
| Installer.install / run_step | — | 进程/文件写 |
| RegistryStore.* | — | 文件 IO |

---

## 6. 启动行为规范

### 6.1 环境组装(证据忠实最小集)

分层覆盖,后者胜:

```
L1  os.environ 拷贝
L2  STEAM_COMPAT_DATA_PATH=<prefix>
    STEAM_COMPAT_CLIENT_INSTALL_PATH=<steam 目录>
L3  PATH 前插:<path_append 逐项> + <proton>/files/bin
L4  清单 env(含 dll_overrides 展开)—— 最高优先级
```

**刻意不设**(与 umu 的差异,均有实证):
- `WINEPREFIX` / `PROTONPATH` / `PROTON_VERB` —— umu 的变量体系,直调 proton 不需要
  (三张验证配方 start-{pvz,ra2,mo3}.sh 均未设 WINEPREFIX 而通)
- `SteamAppId` —— 仅 `game_id` 非零时注入
- `PROTON_LOG` —— 默认不开;用户需要 wine 级日志时经清单 env 自行开启

### 6.2 cwd 契约

```
cwd = manifest.game_dir          # 绝对路径,启动前校验 is_dir(),否则 LaunchError
Popen(cwd=cwd)                   # umu_run.py:742 同款:显式钉住,不依赖默认继承
```

**exe 参数形态契约**(M2 实测血案):exe 在 game_dir 内时,命令行必须传
`./相对` 形式而非绝对路径 —— 绝对路径会让 wine 构造带引号的 Windows 命令行,
PopCap DRM 外壳对其 GetCommandLine() 做字符串手术转发时切歪,真实游戏收到
变形的 -changedir 而 fatal "invalid arguments"。fatal 弹框进程也是"活着"的,
验收时必须用 CPU 占用区分真跑(>50%)与卡报错框(~0%)。

### 6.3 进程管理(umu_run.py:693-747 移植)

1. `prctl(PR_SET_CHILD_SUBREAPER, 1)`(ctypes;argtypes 精确
   `[c_int, c_ulong ×4]`,失败仅告警降级)
2. `Popen(start_new_session=True)` —— 自立会话
3. SIGINT/SIGTERM 处理器:扫 `/proc/*/status` PPid 建树,BFS 收集后代,逐个 kill
   (ProcessLookupError 容忍)—— **只打自己的树,永不 pkill wineserver**
   ⚠ 收割目标是 **os.getpid() 的全部后代**(而非 proton 脚本的子树):
   xalia 会话层会 double-fork 游戏进程出 proton 子树,但我们设了 subreaper,
   被遗弃者会过继给 exebox 本身 —— "我的后代"才是完备集合(M2 实测教训,
   首版曾漏杀 wine loader)。wait 返回后同样清扫一遍兜底。
4. `proc.wait()` 收退出码;负值翻译为"被信号 N 杀死"
5. stdout/stderr → `<箱>/logs/<ISO时间戳>.launch.log`,路径进 LaunchResult

### 6.4 prefix 脚手架(umu setup_pfx L79-121 移植)

新建时创建:根目录 + `shadercache/` + `gstreamer-1.0/` + `tracked_files`(空文件)
+ `pfx -> .` 自指符号链接 + `pfx.lock` 预建(filelock 教训:目录必须先在)
+ `users/steamuser ↔ unixuser` 符号链接三态舞蹈。

**铁律:已有的不动。** `pfx` 无论真目录(直调/Steam 风格)还是符号链接(umu 风格)
一律保持原样;只对缺失的顶层件补缺;绝不做布局转换。

### 6.5 版本棘轮与托管检测

- 启动前读 `<prefix>/version` 与目标 Proton 的 `version` 比对
- 不匹配且**非托管**:交互式提示"升级不可逆,继续?y/N";`--bg`/非交互直接拒启
- **托管检测**(`config_info` 存在或路径含 `compatdata`):版本不符一律拒启,
  建议走 Steam 本体;永不写其 `tracked_files`

---

## 7. install 流程

### 7.1 交互式(默认)

`exebox install [SOURCE.exe]`,8 步向导:

```
1 游戏名(默认取自 exe 文件名)
2 Proton 版本(列出本机可用,默认 Proton - Experimental)
3 prefix 位置(默认 <箱>/prefix;可输入 existing:<路径> 复用现存)
4 game_dir(exe 所在目录)
5 exe 文件名(相对 game_dir)
6 附加项:DLL 覆盖 / args / PATH 追加(可全空)
7 展示生成的 game.yaml 全文 → 确认写入
8 是否立即运行安装器(install.source)
```

### 7.2 非交互式

```
exebox install --manifest F --run-installer    # 读现成清单并跑安装器
exebox install --manifest F --skip-installer   # 仅注册
exebox install --import                        # 向导但跳过第 8 步(存量游戏主路径)
```

### 7.3 step 类型语义(顺序执行,任一失败即中止)

| type | 字段 | 执行方式 |
|---|---|---|
| `shell` | `command: [str]` | 经本工具 ProtonRunner 以同 prefix 执行(享受同一套 env/cwd 契约) |
| `reg_add` | `key/value/value_type/reg_hive/reg_arch` | `proton run reg add … /f [/reg:32\|/reg:64]`(Westwood 键复刻就用它) |
| `copy` | `src/dst` | shutil.copy2,纯文件系统 |
| `mkdir` | `dst` | mkdir -p 语义 |
| `winetricks` | `verb` | **暂缓**(依赖 winetricks 二进制,开放问题 §11) |

---

## 8. CLI 面

| 命令 | 语法 | 说明 |
|---|---|---|
| `list` | `exebox list [--all] [--protons]` | 扁平紧凑表格(rich);`--all` 附健康检查列;`--protons` 列本机 Proton |
| `launch` | `exebox launch <slug> [--dry-run] [--bg] [--env K=V]…` | 启动;`--env` 临时覆盖清单 |
| `install` | 见 §7.2 | 安装/导入 |

输出样式基调(反 Lutris 弹窗):

```
$ exebox list
NAME                        SLUG   PROTON                 PREFIX
Plants vs Zombies           pvz    Proton - Experimental  ~/Documents/codes/games/pvz-exp-prefix
C&C: Red Alert 2 - YR       ra2    Proton - Experimental  …/compatdata/2229850
Mental Omega 3              mo3    Proton - Experimental  ~/Games/mo3

$ exebox launch mo3
[10:30:00] Launching Mental Omega 3
  Proton  Proton - Experimental (11.0-20260805)
  Exe     ./MentalOmegaClient.exe
  Cwd     /home/div/Games/mo3/drive_c/Program Files (x86)/Mental Omega
  Prefix  /home/div/Games/mo3 (11.0-100)
  Env+    WINEDLLOVERRIDES=ddraw=n,b
  PATH+   …/Mental Omega
  Log     ~/Games/exebox/mo3/logs/2026-08-15T10-30-00.launch.log
[10:30:02] pid 42851
[10:45:30] exited 0 (15m28s)
```

`--dry-run` 输出最终命令行 + 全量环境(rich panel),这是零隐藏参数支柱的审计出口。

---

## 9. 里程碑与验证

| 里程碑 | 内容 | 验证(全部用本机现存三游戏) |
|---|---|---|
| M1 骨架+list | uv 项目、models、loader、resolver、registry、cli(list) | 手写三清单后 list 正确显示;list --protons 出三个 Proton |
| M2 launch 简单局 | prefix/manager、runner、process、launcher、dry-run、日志 | launch pvz / ra2 游戏可玩;Ctrl-C 全树干净退出;日志落盘 |
| M3 复杂局+install | path_append、installer/steps、棘轮、托管检测 | launch mo3 全链通(→Syringe→gamemd);用 PvZ 安装器实测 install;dry-run 可见 PATH 注入 |
| M4 打磨 | 异常全覆盖、--bg、空格/非 ASCII 路径警告、README | 错误路径输出人话;三游戏回归 |

---

## 10. 风险与规避

| 风险 | 级别 | 规避 |
|---|---|---|
| prefix 版本棘轮不可逆 | 高 | 启动前强制比对;托管 prefix 版本不符拒启(§6.5) |
| proton 脚本输出无版本化格式 | 中 | 黑盒对待:只收退出码+日志;唯一解析物是 version 文件 |
| 路径含空格(RA2 实锤) | 中 | 全链禁 shell=True;路径尽早 Path 化;校验时告警 |
| prctl argtypes 写错 = 静默踩内存 | 中 | M1 即写冒烟测试;失败降级仅告警 |
| wineserver 误伤 | 中 | 永不 pkill wineserver;信号只打自己的 /proc 树(§6.3) |
| 三种 prefix 布局并存 | 低 | scaffold 只增不改;布局检测不转换(§6.4) |

---

## 11. 开放问题(待定夺)

1. **命名**:exebox 是占位。候选:exebox / prefixman / winbox …(影响库名、
   EXEBOX_HOME 变量名、~/Games 子目录名,越早定越好)
2. **GUI 技术选型**(二期):textual(终端内,与 CLI 同语言零跳转)vs
   PySide6(桌面原生,列表界面更"扁平")—— v1 结束后再议
3. **winetricks step** 是否进 v1:依赖 winetricks 二进制与 protonfixes 交互,
   倾向 M4 后按需加
4. **`launch --bg` 的状态查询**:后台模式是否需要 `exebox ps` 子命令
   (列运行中游戏 + pid + 日志尾),v1 可先不做

---

## 附:行为规范的依据索引

| 规范 | 依据 |
|---|---|
| 环境最小集 | start-{pvz,ra2,mo3}.sh 三张实证配方 |
| cwd 契约 | umu_run.py:724(Path.cwd)、:742(Popen cwd);本机 /proc 验证 |
| subreaper/信号树 | umu_run.py:735(prctl)、:693-697(信号处理器)、:419-448(树遍历) |
| prefix 脚手架 | umu_run.py:79-121(setup_pfx) |
| 版本棘轮 | docs/proton-structure.md(实测 "Upgrading prefix from None to 11.0-100") |
| 零隐藏参数 | GE-Proton protonfixes 3590.py:48(--changedir 血案) |
| PATH 注入的必要性 | MO3 mono Process.Start 实证(docs/proton-usage.md 诊断手册) |
