# exebox 阶段验收报告(v1 = M1–M4)

> 2026-08-15 晚,基于代码实态(62 tests / 1825 行 Python / 4 命令 / 4 箱)逐条对账
> requirements.md 的 FR/NFR 与 implementation-plan.md 的里程碑。
> 图例:✅ 已验收(有实证) · ⚠️ 已实现但验收欠账 · ❌ 未实现

## 一、功能需求对账

- [x] **FR-1** 一程序一箱,删箱即卸 ✅(pvz2:manifest+prefix+game+logs 同箱,实测)
- [x] **FR-2** 声明式 YAML 唯一真相 ✅(严格校验:未知字段报错,17 个 loader 测试)
- [x] **FR-3** 清单可引用箱外路径 ✅(pvz/ra2 外置 prefix 与游戏文件)
- [ ] **FR-4** 清单 schema 版本字段 ❌(未实现,列入 v1.2)
- [x] **FR-5** `list [--all|--protons]` ✅(健康列/告警/四引擎实测)
- [x] **FR-6** `launch --dry-run/--env` ✅(增量环境视图+机密打码;dry-run 语义与黄金配方对账)
- [x] **FR-7** install:向导 + `--manifest/--import/--run-installer` ⚠️(非交互路径实测通过;**交互向导未做 E2E**,列入 v1.1)
- [x] **FR-8** 安装步骤原语 shell/reg_add/copy/mkdir ⚠️(单测全覆盖含命令行拼接;**reg_add 未真机验证**,列入 v1.1)
- [x] **FR-9** `--bg` + `ps` ⚠️(实现+ps 实测;`--bg` 在 fork 炸弹清场后**未复测**,列入 v1.1)
- [ ] **FR-10** `doctor` ❌(S 级,未实现,列入 v1.2)
- [x] **FR-11** Proton 发现(双位置+模糊) ✅(真机 4 引擎,含模糊命中测试)
- [x] **FR-12** prefix 脚手架(只增不改) ✅(三种布局检测+幂等测试)
- [x] **FR-13** 版本棘轮防护 ✅(真机演练:非交互拒启/交互确认/托管硬拒三路)
- [x] **FR-14** 托管 prefix 只读 ✅(steamapps/compatdata 形态识别,config_info 误判已修)
- [ ] **FR-15** prefix `reset`/`shell` ❌(S 级,未实现,列入 v1.2)
- [x] **FR-16** subreaper + 信号全树收割 ✅(双游戏 SIGINT 零幸存;僵尸处理有专门回归)
- [x] **FR-17** 可靠退出码 ✅(exit 0/被信号N杀死/非零三态如实报告)
- [x] **FR-18** 永不误伤邻居 ⚠️(单箱树作用域已证;**双游戏并行**场景未显式测试,列入 v1.1)
- [x] **FR-19** 每启一份日志 ✅(箱内 logs/,路径进输出)
- [x] **FR-20** 零隐藏参数 ✅(dry-run 全量可审计;黄金快照含负向断言)

## 二、非功能需求对账

- [x] **NFR-1** 可审计性 ✅(`launch --dry-run`;清单外字段=0 由测试保证)
- [x] **NFR-2** 可版本化 ✅(纯文本 YAML;registry.json 在箱外仅缓存)
- [x] **NFR-3** 依赖最小 ✅(运行时 3 个:pyyaml/rich/typer;无守护进程;不联网)
- [x] **NFR-4** 性能 ✅(实测 `list` 65ms)
- [x] **NFR-5** 健壮性 ✅(全局错误人话化,坏清单不拖垮 list)
- [x] **NFR-6** 可测试性 ✅(core 纯逻辑可注入假世界;62 单测 3.2s)
- [x] **NFR-7** 文档一致性 ✅(设计文档 §6 随每只 bug 同步,含实证行号)
- [x] **NFR-8** 安全边界 ✅(`shell=True` 全仓 0 处;路径全 Path 化;不提权)

## 三、里程碑

- [x] **M1** 骨架+list ✅(tag m1)
- [x] **M2** launch+进程树 ✅(tag m2;含相对路径血案修复)
- [x] **M3** install+棘轮 ✅(tag m3;含生命周期三连修复)
- [x] **M4** 打磨 ✅(tag m4;--bg/ps/告警/README/全局错误)

## 四、验收欠账清单(v1.1 已全部销账 2026-08-15 晚)

| # | 结果 | 备注 |
|---|---|---|
| D1 交互向导 E2E | ✅ | 管道喂答案 → 清单生成 → 全新 prefix → **原版 RA2(game.exe)首测成功**;附带发现:向导 Proton 列表 compat 优先,默认 1 号是 GE 而非官方(记 v1.2 待议) |
| D2 reg_add 真机 | ✅ | Westwood 三件套落 Wow6432Node(REG_SZ+DWORD),与晨间手抄作业逐字节等价;附带发现:CLI 缺 steps-only 入口(记 v1.2) |
| D3 --bg 全链 | ✅ | 启动→CPU 77%→kill→树清零→bg 进程退场;**挖出并修复真 bug:TERM 免疫的 wine 陪跑致等待循环挂死(现 SIGKILL 升级 + 30s 耐心上限,含回归测试)** |
| D4 并行误伤 | ✅ | pvz+ra2 双活,杀 pvz 后 ra2 的 exebox 与游戏进程分毫未伤 |

git 历史整理 ✅:9 条同名 m3 提交(炸弹空转产物)squash 为 1 条并改写信息,
tags m1–m4 全部有效;事故复盘见 [lessons-forkbomb.md](lessons-forkbomb.md)。

## 五、已知限制(如实)

1. MO3 等引导器程序:exebox 在引导壳退出后数秒返回(xalia 把子树移出族谱),游戏无恙;前台等待完全保真未做
2. GUI 安装器兼容不保证(PopCap 安装器实测 exit 0 不落文件);便携拷贝路线已验证

## 六、下一阶段规划

**v1.1 补验收 ✅ 已完成**
- [x] D1–D4 四项欠账逐一销账(详见第四节)
- [x] git 历史整理(9→1 squash,需 force-push 同步 remote,待用户确认)
- [x] 事故复盘归档(docs/lessons-forkbomb.md)
- [x] 新增:顽固子代 SIGKILL 升级(真 bug 修复 + 回归测试,63 tests)

**v1.2 完形(一至两天)**
- [ ] 向导默认 Proton 改为官方 Experimental(若存在);CLI steps-only 安装入口
- [ ] FR-4 清单 schema 版本字段 + 迁移策略
- [ ] FR-15 `exebox prefix reset|shell`(类 docker exec 体验)
- [ ] FR-10 `exebox doctor <slug>`(体检+修复建议,诊断手册产品化)
- [ ] MO3 前台等待保真(按 prefix 关联 wineserver 存活判定)

**v1.3 走向用户 ✅ 已完成(2026-08-16)**
- [x] 命名定稿:**exebox**(PyPI 可用、零迁移)
- [x] 发布准备:pyproject 1.3.0 完整元数据/MIT License/README.en.md;
  uv build 产物隔离验证可装可跑;**PyPI 上传暂缓**(按用户决定,仓库安装即可)
- [x] 非游戏验收三连(U1 迁移者画像端到端):
  - 7-Zip(自家安装器/无参数静默):装→CLI 打包功能验证(209B 压缩包);
    发现 26.x 弃用 Inno,/VERYSILENT 被拒 —— install.args 需按安装器家族选参
  - Notepad++(NSIS /S):静默装→launch 存活→收割干净
  - **VS Code User Setup(重型 Inno/225MB)**:/VERYSILENT 静默装→
    11 个 Electron 进程/6.4GB RSS→bg 会话同寿→kill 零残活→doctor 6 项 ok
- [x] schema 新增 install.args(安装器参数)+ 测试
- [x] 边界发现:codex desktop(ChatGPT Desktop)为 MS Store/MSIX 分发,
  无传统 .exe —— 商店分发形态明确落在 exebox 射程外(以 VS Code 补重型样本)

**v2 GUI(排期另定)**
- [ ] 技术选型 spike(textual vs PySide,各做一个箱列表原型)
- [ ] GUI 复用 core(NFR-6 已铺路)

## 七、结论

v1 承诺的核心(list/launch/install 三件事 + 零隐藏参数 + 箱模型 + 进程树治理)
**全部兑现且有实证**;欠账集中在交互路径的 E2E 与三个 S 级功能,已排入 v1.1/v1.2。
