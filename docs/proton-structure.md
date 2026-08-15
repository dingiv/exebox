# Proton / Wine 目录结构与组织

## 三层模型

```
第一层  Proton 本体(引擎,只读,可被所有游戏共享)
第二层  compatdata 容器(Proton 特有,每个 appid 一个,STEAM_COMPAT_DATA_PATH 指向它)
第三层  pfx —— 真·wine prefix(一台"假电脑",WINEPREFIX 指向它)
```

裸 wine 用户直接操作第三层(`WINEPREFIX=~/.wine`);Proton 把第三层包进第二层。

---

## 第一层:Proton 本体

两个合法安装位:

```
~/.local/share/Steam/steamapps/common/Proton - Experimental/   ← Steam 下载并自动更新
~/.local/share/Steam/compatibilitytools.d/<名字>/              ← 手动放的第三方(GE/UMU)
```

内部结构(实测):

```
Proton - Experimental/
├── proton                ★ 唯一入口,Python 脚本(proton run/wait/bootstrap)
├── version               版本标识("11.0-100"),prefix 升级判断用
├── filelock.py           pfx.lock 的实现(目录不存在会 FileNotFoundError)
├── toolmanifest.vdf      向 Steam 声明"我是兼容工具"
├── files/
│   ├── bin/              wine/wineserver 可执行文件
│   ├── lib/wine/         Windows 侧内置 DLL(kernel32/ddraw/…)
│   └── share/xalia/      Experimental 特有的 .NET 会话组件(日志噪音来源)
└── dist.lock / proton_3.7_tracked_files / …
```

要点:
- `compatibilitytools.d` 是 Steam 扫描第三方 Proton 的位置;GE-Proton 解压到这里即被 Steam 识别
- 换 Proton 版本 = 换第一层;**不需要动游戏和 prefix**(但见下文版本棘轮)

---

## 第二层:compatdata 容器

```
compatdata/2229850/            ← appid(RA2)
├── pfx/          ← 里面才是真 prefix(第三层)
├── pfx.lock      ← 并发锁(所以 STEAM_COMPAT_DATA_PATH 指向的目录必须预先 mkdir!)
├── tracked_files ← Proton 装过哪些系统组件,升级对账用
├── version       ← "11.0-100":上次运行它的 Proton 版本
└── config_info
```

**版本棘轮**:Proton 见旧版本 prefix 会自动升级(日志:`Upgrading prefix from None to 11.0-100`),
单向不可逆。不同版本 Proton 混用同一 prefix = 注册表格式冲突 → 玄学崩溃。
**要换版本测试,新开 prefix 目录。**

---

## 第三层:pfx(一台假电脑)

```
pfx/
├── drive_c/                 假 C 盘,就是普通目录树
│   ├── windows/system32/    wine 内置 DLL 挂载点 + 安装的运行库
│   ├── "Program Files (x86)/"  游戏常住地(如 MO3)
│   ├── ProgramData/         PvZ 的 DRM 会往这解包真实 exe
│   └── users/steamuser/     "我的文档"。Proton 固定用户名 steamuser,
│                            裸 wine 才用 $USER —— 备份存档别找错人
├── dosdevices/              盘符映射表,全是符号链接:
│   ├── c: → ../drive_c      C 盘
│   ├── z: → /               Z 盘 = 整个 Linux 根目录!
│   ├── d: → /mnt/games      外接盘同理
│   └── com1 → /dev/ttyS0    设备也能映射
├── system.reg               注册表 HKLM(纯文本!)
├── user.reg                 注册表 HKCU
└── userdef.reg / .update-timestamp / …
```

关键认识:

1. **游戏眼中的 `C:\...` = 磁盘上的 `drive_c/...`**。给游戏搬家就是 `mv`,搬完记得改注册表里的
   InstallPath(如 Westwood 键)。
2. **注册表是文本文件**:可 grep、可整段复制(从旧 prefix 抄作业)。但 wineserver 活着时会回写,
   要么先杀 wineserver,要么走 `proton run reg add ... /f`(推荐,32 位程序记得 `/reg:32`)。
3. **DLL 加载顺序**:游戏目录 > DllOverrides(注册表 `HKLM\Software\Wine\DllOverrides`)
   > wine 内置。游戏目录放一颗 `ddraw.dll` 通常能生效;`ddraw=native,builtin` 写在 DllOverrides。
4. **z:→/ 是把双刃剑**:游戏因此能读全盘;但 VS Code 的 rg `--follow --no-ignore` 会顺着它
   全盘扫描(实测 736% CPU)。本机已在 settings.json 的 `files.watcherExclude` 排除。

---

## 硬性要求与坑(全部实证)

| 要求 | 违反后果 |
|---|---|
| `STEAM_COMPAT_DATA_PATH` 指向的目录**预先 mkdir** | pfx.lock FileNotFoundError,启动秒退 |
| prefix/游戏路径**避免空格与非 ASCII** | 工具链容忍度不一;MO3 在 `Program Files (x86)` 被 mono 相对路径解析坑过,被迫写绝对路径 |
| 一个 prefix 只侍奉一个 Proton 版本 | 注册表不兼容,玄学崩溃 |
| 别把 prefix 放进会被索引的工作区 | dosdevices 符号链接 → rg 全盘扫描 |
| 杀 wineserver = 拔整台假电脑的电源 | 同 prefix 所有进程孤儿化;`pkill -x wineserver` 不分 prefix,会误伤(本机误杀 PvZ 惨案) |
| 注册表改动要么先停 wine、要么走 reg add | 手改 system.reg 会被 wineserver 回写覆盖 |
