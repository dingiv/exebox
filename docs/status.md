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

## 四、验收欠账清单(v1.1 必须补)

| # | 欠账 | 原因 |
|---|---|---|
| D1 | 交互向导 E2E | fork 炸弹期间无法做交互测试 |
| D2 | reg_add 真机验证(Westwood 键复刻场景) | 未安排 |
| D3 | `--bg` 清场后复测(装→玩→kill 全链) | 同 D1 |
| D4 | 双游戏并行互不误伤 | 只做了串行 |

## 五、已知限制(如实)

1. MO3 等引导器程序:exebox 在引导壳退出后数秒返回(xalia 把子树移出族谱),游戏无恙;前台等待完全保真未做
2. GUI 安装器兼容不保证(PopCap 安装器实测 exit 0 不落文件);便携拷贝路线已验证
3. git 历史有 5 条同名 m3 提交(fork 炸弹空转产物)—— 建议整理,待用户批准

## 六、下一阶段规划

**v1.1 补验收(半天)**
- [ ] D1–D4 四项欠账逐一销账
- [ ] git 历史整理(squash 重复 m3 提交,征得同意后)
- [ ] 清理期事故复盘归档(docs/lessons-forkbomb.md)

**v1.2 完形(一至两天)**
- [ ] FR-4 清单 schema 版本字段 + 迁移策略
- [ ] FR-15 `exebox prefix reset|shell`(类 docker exec 体验)
- [ ] FR-10 `exebox doctor <slug>`(体检+修复建议,诊断手册产品化)
- [ ] MO3 前台等待保真(按 prefix 关联 wineserver 存活判定)

**v1.3 走向用户(两天)**
- [ ] 命名定稿(影响包名/EXEBOX_HOME/目录,越早越好)
- [ ] 发布:PyPI/uvx 一键安装 + README 英文版
- [ ] 非游戏程序验收(requirements 开放问题 #3:选一个有安装器+注册表+DLL 依赖的 Windows 工具走全流程)

**v2 GUI(排期另定)**
- [ ] 技术选型 spike(textual vs PySide,各做一个箱列表原型)
- [ ] GUI 复用 core(NFR-6 已铺路)

## 七、结论

v1 承诺的核心(list/launch/install 三件事 + 零隐藏参数 + 箱模型 + 进程树治理)
**全部兑现且有实证**;欠账集中在交互路径的 E2E 与三个 S 级功能,已排入 v1.1/v1.2。
