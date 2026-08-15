# 进程树与生命周期

## 通用调用链(umu 方式,全链源码/实证标注)

```
你的 shell / Lutris
│  cd 游戏目录                          ← cwd 的真正提供者(Lutris 默认 exe 目录)
│
├─ umu-run(Python zipapp)
│    ├─ 环境组装:GAMEID→SteamAppId、WINEPREFIX→STEAM_COMPAT_DATA_PATH
│    ├─ cwd 契约:Path.cwd() → Popen(cwd=…)   忠实转发,不设置(umu_run.py:724/742)
│    ├─ PR_SET_CHILD_SUBREAPER(自封子收割者)  (umu_run.py:736)
│    └─ start_new_session=True(自立会话)
│
└─ proton(Python 脚本)
     ├─ 初始化/升级 prefix(检查 version 棘轮)
     ├─ PATH 前插自己的 bin                  (proton:1590 prepend_to_env_str)
     └─ 启动 wine loader(WoW64:64 位容器跑 32 位程序)
          │
          ├─ wineserver      ← 每个 prefix 一个,"假内核":窗口句柄/注册表/进程同步/文件锁
          ├─ services.exe / winedevice.exe / plugplay.exe / svchost.exe
          │  rpcss.exe / explorer.exe(/desktop 虚拟桌面)/ tabtip.exe   ← 服务陪跑团
          ├─ xalia.exe       ← Proton Experimental 特有会话组件(.NET)
          └─ <游戏>.exe
```

要点:
- **一个 prefix = 一台假电脑**,wineserver 是它的内核;不同游戏的 wineserver 互不相干
- 直连 `proton run`(不经 umu)时,链上少了 umu 的 subreaper/信号管理,
  xalia 会话层的行为差异会放大(吞输出、env 不透传、生命周期错乱)

---

## MO3 特例:Syringe 调试器注入链

CnCNet 系 mod 客户端的标准结构,也是全链最脆的一环:

```
MentalOmegaClient.exe(.NET 引导器,mono 运行时扛着)
└─ Resources\clientdx.exe(真身:CnCNet 客户端 UI)
     ├─ 读 ClientDefinitions.ini / RA2MO.ini / Renderers.ini
     ├─ 渲染器管理:把 Resources\cnc-ddraw.dll+ini 复制成游戏根目录 ddraw.dll+ini
     ├─ 写 spawn.ini + spawnmap.ini(选好的地图/阵营/规则)
     └─ Process.Start(GameLauncherExecutableName, "gamemd.exe -SPAWN -CD …")
          │  ⚠ mono 只认绝对路径/PATH,不搜 cwd
          │  → 修复:ClientDefinitions.ini 里写 C:\ 绝对路径
          │
          └─ Syringe.exe(以调试器身份工作)
               ├─ 解析 gamemd.exe PE 头(入口点/CRC/时间戳)
               ├─ 识别 *.dll.inj → Ares.dll 握手
               │    "Found Yuri's Revenge 1.001 (UC). Applying Ares 3.0"(1448 hooks)
               ├─ CreateProcess(gamemd.exe, DEBUG_ONLY_THIS_PROCESS)
               └─ 调试循环:断点拦截 → 0x150000 写入 loader → 入口前 LoadLibrary("Ares.dll")
                    │
                    └─ gamemd.exe(尤里复仇引擎)
                         ├─ -SPAWN → 遭遇战模式,读 spawn.ini
                         ├─ DirectDraw 初始化 → 加载游戏根目录 ddraw.dll
                         │    └─ cnc-ddraw:ddraw.ini(renderer=opengl)→ 翻译成 OpenGL
                         └─ .mix 资源 + Ares 扩展规则 → 对局
```

判断注入成功的标志:`syringe.log` 出现
`HandleException: Creating code hooks` 且无 `0x80000100` 之类异常码。

---

## cwd 的完整传递链(谁保证游戏的工作目录正确)

```
调用者 cd(Lutris 默认 = exe 目录:wine.py:373-375)
  → exec umu-run:继承,不改
  → Popen(proton, cwd=Path.cwd()):显式钉住(umu_run.py:724,742)
  → proton:不动
  → wine 进程创建:unix cwd 经 dosdevices 的 z:→/ 映射,翻译成 "Z:\…" Windows cwd
```

实证:`readlink /proc/<游戏pid>/cwd` = 游戏目录;wine 日志满地 `Z:/home/...` 路径。

---

## 生命周期管理

- **正常退出**:umu 方式下 Ctrl-C/kill umu → 信号处理器遍历进程树逐一收割,干净
- **直连方式**:proton 脚本退出后,游戏进程可能成为孤儿继续活(xalia 会话),判断"死没死"
  要看真实进程,不能只看启动命令的退出码
- **核弹级**:`pkill -x wineserver` = 给所有假电脑拔电源
  - 同 prefix 全部进程孤儿化(进程变 `<defunct>` 或带服务陪跑团游荡)
  - **不分 prefix,会误伤其他游戏**(本机实锤:PvZ 阵亡)
  - 仅在确认目标 prefix 的进程可牺牲时使用;更稳的做法是杀具体游戏进程
- **幽灵锁**:游戏崩溃后 wineserver 若存活,可能攥着文件锁让下次启动的客户端卡死
  (症状:`Timeout waiting for exclusive access`)。解法:清掉该 prefix 的残留 wine 进程

---

## 观察工具箱

```bash
# 全量看 Windows 进程(别用单一 pgrep 模式)
ps -eo pid,ppid,etime,args | grep -iE "\.exe" | grep -vE "grep|bash -c"

# 进程树全景
pstree -p | grep -A20 <锚点进程名>

# 进程真相三件套
readlink /proc/<pid>/cwd                          # 工作目录
tr '\0' '\n' < /proc/<pid>/environ | grep -E "PATH|WINE"   # 环境
cat /proc/<pid>/cmdline | tr '\0' ' '             # 完整命令行

# 每个 prefix 的 wineserver
pgrep -ax wineserver
```
