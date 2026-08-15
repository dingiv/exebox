# Proton / Wine 游戏环境文档

> 2026-08-15 实证归档。所有路径、行为、源码行号均来自本机验证
> (Proton Experimental `11.0-20260805`、umu-launcher 1.4.4、Lutris 0.5.22),
> 非通用 Wiki 转述。

## 一句话模型

**引擎与电脑分离**:Proton/wine 是引擎(可执行程序),prefix 是每个游戏专属的"假电脑"(数据目录)。同一引擎 + 不同 prefix = 平行世界。

Proton 仿真的是 Windows,Steam 仿真的是发行环境 —— 游戏离 Steam 发行环境越近(Steamworks、启动器套娃、相对路径解析),越需要"那半个 Steam"(umu/Lutris/真 Steam)。

## 目录

| 文档 | 内容 |
|---|---|
| [requirements.md](requirements.md) | **需求文档**:产品愿景、用户画像、用户故事、功能/非功能需求、验收标准 |
| [implementation-plan.md](implementation-plan.md) | **实现方案/施工图**:工程决策、M1-M4 文件级施工图、黄金快照测试、命令卡 |
| [exebox-design.md](exebox-design.md) | **设计文档**(草案 v1,未实现):使命/清单 schema/架构/行为规范/里程碑 |
| [research-alternatives.md](research-alternatives.md) | **竞品调研**(2026-08):全景对照 + 精确生态位 + 空白矩阵 + 造轮子结论 |
| [proton-structure.md](proton-structure.md) | 三层目录模型、prefix 解剖、dosdevices、注册表、硬性要求与坑 |
| [proton-usage.md](proton-usage.md) | 三种启动方式、环境变量参考、诊断手册 |
| [process-tree.md](process-tree.md) | 进程调用链、wine 会话模型、Syringe 注入、生命周期管理 |

## 本机地图

```
~/.local/share/Steam/
├── steamapps/common/Proton - Experimental/          官方 Proton(Steam 自动更新)
├── compatibilitytools.d/GE-Proton11-3               第三方 Proton(GE / UMU-Proton 同住)
└── steamapps/compatdata/<appid>/                    Steam 游戏的 prefix 容器(RA2=2229850)

~/Games/mo3/                                         Lutris/umu 的 MO3 prefix
~/Documents/codes/games/pvz-exp-prefix/              手搓的 PvZ prefix
~/Documents/codes/games/src/{umu-launcher,lutris}    源码(浅克隆,考古用)
~/Documents/codes/games/start-{pvz,ra2,mo3}.sh       三个游戏的启动脚本
```

## 本机战绩

- PvZ(2009 原版):直连 proton run ✅
- RA2+尤里(Steam 版):直连 proton run ✅
- 心灵终结 MO3:umu-run 配方 ✅(三阶段攻坚:mono 进程解析 → ddraw 渲染器 → DLL 加载)
