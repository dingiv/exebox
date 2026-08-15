# exebox

> wine/proton 的前端 —— 快速方便地在 Linux 上玩转 exe 程序,把 Windows 软件迁移到 Linux 平台。
> 易用性与专业性/灵活性/底层能力暴露,我们选择尽可能都要。

一个程序 = 一个"箱"(manifest + prefix + 游戏文件 + 日志,同目录,`rm -rf` 即彻底卸载),
声明式清单(类 docker-compose),CLI 优先,**清单之外零隐藏参数**。

## 安装

```bash
git clone <repo> && cd exebox
uv sync            # 需要 uv(pip install uv / curl 系)
uv run exebox --help
```

可选:alias `exebox="uv run --project ~/path/to/exebox exebox"`。

## 快速上手

```bash
# 交互向导:8 步生成清单(可先跑一遍看生成的 game.yaml)
exebox install /path/to/setup.exe

# 或手写清单(推荐,编辑器即 UI)
mkdir -p ~/Games/exebox/mygame
$EDITOR ~/Games/exebox/mygame/game.yaml

exebox list                 # 一张表看全家底
exebox list --protons       # 本机可用引擎
exebox launch mygame        # 开玩
exebox launch mygame --dry-run   # 审计:将执行的命令与环境全量可见
exebox launch mygame --bg   # 后台;exebox ps 查看,kill <PID> 整树收割
```

## 清单(game.yaml)

```yaml
name: 心灵终结 3
exe: ./MentalOmegaClient.exe      # 相对 game_dir;exebox 会以 ./相对 形式传给
                                   # proton(PopCap 类 DRM 外壳对绝对路径过敏)
proton: Proton - Experimental      # 名称或模糊名,自动解析本机已装版本
prefix: /home/you/Games/mo3        # compatdata 根,可外置复用(如 Steam compatdata)
game_dir: /home/you/Games/mo3/drive_c/Program Files (x86)/Mental Omega   # 启动 cwd,绝不猜测
dll_overrides: "ddraw=n,b"         # env.WINEDLLOVERRIDES 的简写
path_append:                       # 启动时前插 PATH(启动器套娃/mono 解析场景)
  - /home/you/Games/mo3/drive_c/Program Files (x86)/Mental Omega
args: []                           # 原样追加到 exe 命令行
game_id: 0                         # 0 = 完全不设 SteamAppId(不伪造 Steam 身份)
notes: >
  启动链 client→clientdx→Syringe→gamemd;mono 靠 PATH 解析相对名。
```

完整 schema 与三个真实样例见 [docs/exebox-design.md](docs/exebox-design.md) 与
[examples/](examples/)。**未知字段一律报错** —— 拼错键名当场炸,绝不静默忽略。

## 设计支柱

1. **零隐藏参数**:直调官方 Proton(无 protonfixes 按 ID 偷塞参数)、不经
   `wine start` 重写命令行、`--dry-run` 全量可审计
2. **自研薄层**:不依赖 umu/Lutris 运行时;subreaper + 信号全树收割
   (Ctrl-C 干净退场,绝不误伤别的游戏)
3. **core 即库**:全部逻辑返回数据/抛异常,CLI 与未来 GUI 共用同一 core

## 行为契约(踩坑换来的,测试焊死)

- prefix 版本棘轮:与目标 Proton 不一致时,自建 prefix 需确认、Steam 托管
  prefix(steamapps/compatdata)一律拒启 —— 升级不可逆
- exe 在 game_dir 内时命令行用 `./相对` 形式(绝对路径会被 wine 引号化,
  令 PopCap DRM 外壳的命令行手术切歪)
- 引导器程序(壳拉起真身即退)会等真身跑完;Ctrl-C 杀整树;僵尸不算活人
- 环境最小集:只设 `STEAM_COMPAT_*`(+清单显式项);刻意不设
  WINEPREFIX/PROTONPATH/PROTON_VERB

## 文档

- [需求](docs/requirements.md) · [设计](docs/exebox-design.md) ·
  [实现方案](docs/implementation-plan.md) · [竞品调研](docs/research-alternatives.md)
- Proton 底层实证(目录/用法/进程树):[docs/](docs/README.md)

## 状态

M1-M4 完结:四箱实战验证(PvZ / RA2尤里 / 心灵终结 / 全新箱安装),
62 单测(含三游戏黄金快照回归)。
