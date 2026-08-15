# Proton 使用方法

## 三种启动方式(按侵入性递增)

### 方式一:直连 `proton run`(适合简单单机游戏)

```bash
cd <游戏目录>        # ★ 必须!老引擎按相对路径找资源文件,不 cd 会静默秒退
mkdir -p <prefix目录> # ★ 必须!Proton 的 filelock 不会自建目录
STEAM_COMPAT_DATA_PATH=<prefix目录> \
STEAM_COMPAT_CLIENT_INSTALL_PATH=~/.local/share/Steam \
"~/.local/share/Steam/steamapps/common/Proton - Experimental/proton" \
run ./game.exe
```

本机实证:PvZ、RA2(gamemd.exe)均一次跑通。

已知局限(Proton Experimental 的 xalia 会话层):
- 子进程 stdout 可能被吞(`cmd /c ver` 无输出)
- `proton run` 脚本退出 ≠ 游戏退出(进程可能还在,也可能反着)
- 环境变量注入(PATH 等)不可靠
- .NET 程序的 `Process.Start("相对名.exe")` 解析不到(cwd 不参与搜索)

→ 凡是"游戏再拉起子进程"的结构(启动器/mod 客户端),直接上方式二。

### 方式二:umu-run(适合启动器类游戏,标准解)

umu 是社区标准的"假 Steam 客户端":补齐 Steam 启动游戏时提供的环境。
Lutris/Heroic/Bottles 底层都用它。本机用 Lutris 自带的 zipapp(宿主机可直接跑):

```bash
export GAMEID=0
export PROTONPATH="~/.local/share/Steam/steamapps/common/Proton - Experimental"
export WINEPREFIX=<compatdata 风格的 prefix>   # umu 会把它当 compatdata,内含 pfx/
cd <游戏目录>
exec ~/.var/app/net.lutris.Lutris/data/lutris/runtime/umu/umu-run ./game.exe
```

完整可运行样例见 `~/Documents/codes/games/start-mo3.sh`。

umu 的行为契约(源码实证,umu_run.py):
- **不设置 cwd,忠实转发**:`cwd = Path.cwd()` → `Popen(command, cwd=cwd)`(L724/L742)
- 不动你的环境变量,只补 Steam 侧的(GAMEID/STEAM_COMPAT_DATA_PATH/…)
- `PR_SET_CHILD_SUBREAPER`(L736)+ `start_new_session=True` + 信号处理器遍历进程树
  → 生命周期干净,Ctrl-C 全树收割
- 唯一 chdir 特例:winetricks(L720-722)

### 方式三:Lutris / 真 Steam(图形界面)

- **Lutris**:GUI 配游戏(exe、prefix、wine 版本),底层经 umu 跑 Proton。
  DLL 覆盖 GUI 设置 → `WINEDLLOVERRIDES`(lutris 源码 runners/commands/wine.py:182/416)。
  working_dir 默认 = exe 所在目录(wine.py:373-375)。
- **真 Steam 添加非 Steam 游戏**:最好的"假 Steam"就是真 Steam —— 环境最完整,
  白送兼容性工具切换 UI 和游戏内覆盖层。要"点图标就玩"的终极体验,选这条。

---

## 环境变量参考

| 变量 | 作用 | 备注 |
|---|---|---|
| `STEAM_COMPAT_DATA_PATH` | Proton 的 compatdata 容器 | 必须预存在;内含 pfx/ |
| `STEAM_COMPAT_CLIENT_INSTALL_PATH` | Steam 安装目录 | 无 Steam 客户端在场时的正规补丁 |
| `WINEPREFIX` | 直接指 wine prefix | umu 语境下指 compatdata 根(内含 pfx/) |
| `PROTONPATH` | 指定 Proton 版本 | umu/脚本用;不设则自动探测 |
| `GAMEID` | umu 的假 appid | 影响 protonfixes 匹配 |
| `WINEDLLOVERRIDES` | DLL 加载覆盖 | 如 `ddraw=n,b`;等价注册表 DllOverrides |
| `PROTON_LOG=1` | 输出 wine 日志到 `~/steam-<pid>.log` | 本机 Experimental 下偶有不出日志的情况 |
| `WINEDEBUG=+relay` | 全量 API 追踪 | 日志巨大,只用于验尸 |
| `WINEDEBUG=-all` | 关闭调试输出 | 降噪 |

---

## 诊断手册(本机实证套路)

1. **进程真相**:`ps -eo pid,ppid,etime,args | grep -iE "\.exe" | grep -vE "grep|bash -c"`
   —— 不要信单一 pgrep 模式(Windows 进程名五花八门:MentalOmegaClient 只是引导器,
   真身是 Resources\clientdx.exe)
2. **进程的 cwd 和环境**:`readlink /proc/<pid>/cwd`、`tr '\0' '\n' < /proc/<pid>/environ`
3. **注册表取证**:`grep -F -A3 '键名' <prefix>/pfx/system.reg`(注意双反斜杠转义,
   固定字符串用 `grep -F`)
4. **游戏侧日志**:CnCNet 客户端在 `<游戏>/Client/client.log`;Syringe 在 `<游戏>/syringe.log`
5. **wine 内建命令输出被吞时**:让命令把结果写进文件再 cat,别指望 stdout

### pgrep/监控脚本三戒(血泪)

- 模式用 `[g]amemd` 方括号法防自匹配 —— **但这只防了一半**
- **echo/提示文案里不能含目标进程名字面量**(如 "gamemd.exe 已启动"),否则 bash -c 包装进程
  的 cmdline 依然会被 pgrep -f 命中,秒误报
- 判"客户端死亡"前先弄清它的真实进程名(clientdx.exe ≠ MentalOmegaClient.exe)
