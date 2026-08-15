# exebox 实现方案(施工图)

> v1(2026-08-15)。上游文档:[requirements.md](requirements.md)(要什么)、
> [exebox-design.md](exebox-design.md)(架构与行为规范)。
> 本文档回答:**按什么顺序、写哪些文件、每步怎么算完成**。

---

## 1. 总体策略

- **里程碑制**:M1→M4,每个里程碑独立可验证、可提交(git commit 粒度 = 里程碑内步骤)
- **测试先行于 E2E**:纯逻辑(环境组装/命令构造/清单解析)单测覆盖;
  真机 E2E 用三款存量游戏,标记 `e2e` 慢测
- **黄金快照回归**:把三张实证配方(start-*.sh 的环境/命令等价物)固化为
  断言 —— 谁改坏了启动行为,CI/pytest 立刻知道
- **文档同步纪律**:行为变更必须同步 exebox-design.md §6(行为规范是合约)

## 2. 工程决策

| 决策 | 选择 | 说明 |
|---|---|---|
| 包管理 | uv(`uv add` / `uv sync` / `uv run`) | 本机无 pip,uv 0.11.1 在位 |
| 布局 | 平铺 `exebox/` 包 + `tests/{unit,e2e}/` | 与设计文档 §5 一致 |
| 运行依赖 | `pyyaml` `rich` `typer` | 手动校验清单,不引 pydantic |
| 开发依赖 | `pytest` `ruff` | ruff 可选但强烈建议 |
| 构建 | hatchling + `[project.scripts] exebox = "exebox.cli:app"` | uv init 的 pyproject 需补 build-system |
| 遗留清理 | 删除 uv init 生成的 `main.py` | 入口统一走 cli.py |
| Python | >=3.13(`.python-version` 已定) | |

## 3. M1 施工图:骨架 + `list`

**目标**:项目可安装、清单可解析、家底可列举。零进程副作用。

文件清单(自底向上):

```
pyproject.toml                    # 补 build-system/deps/scripts,删 main.py
exebox/__init__.py                # 版本号 + 公共 API 再导出
exebox/errors.py                  # 异常层级(design §附录 B)
exebox/models.py                  # 7 个 dataclass(design §5.2)
exebox/config.py                  # Config:lIBRARY_ROOT/PROTON_HOME,EXEBOX_* 覆盖
exebox/manifest/__init__.py
exebox/manifest/loader.py         # load(path)->GameManifest;路径解析(相对→箱根);校验
exebox/proton/__init__.py
exebox/proton/resolver.py         # list_available/resolve(名称→目录,模糊匹配)
exebox/registry/__init__.py
exebox/registry/store.py          # registry.json 缓存 + rescan
exebox/cli.py                     # typer:list [--all|--protons]
examples/{pvz,ra2,mo3}.yaml       # 仓库内样例(实际清单放 ~/Games/exebox/)
tests/unit/test_models.py
tests/unit/test_manifest_loader.py
tests/unit/test_proton_resolver.py
```

关键实现点:

- `loader`:YAML → dict → 逐字段校验(类型/必填/路径存在性警告)→ Path 解析
  (`exe` 相对 `game_dir`;`game_dir`/`prefix` 相对箱根)→ dataclass。
  未知字段**报错**(零隐藏参数:拼错键名必须炸,不能静默忽略)
- `resolver`:扫 `compatibilitytools.d/` 与 `steamapps/common/`,凡含可执行
  `proton` 脚本的目录即为版本;读 `version` 文件;模糊匹配 = 去空格小写比较
- `store`:rescan 扫 `LIBRARY_ROOT/*/game.yaml`;registry.json 记
  `{slug: {name, box_path, manifest_hash}}`;加载时 hash 不符自动重读清单

**完成判据**(全部 `uv run` 前缀):
1. `uv run pytest` 绿(≥15 个断言:坏清单炸、好清单字段全对、模糊名命中)
2. 三清单放 `~/Games/exebox/` 后 `exebox list` 出三行,列:NAME/SLUG/PROTON/PREFIX
3. `exebox list --protons` 出本机 3 个 Proton(Experimental/GE11-3/UMU10.0-4)
4. `exebox list --all` 健康列全绿(exe 存在/prefix 存在/版本匹配)

## 4. M2 施工图:`launch`(简单局,PvZ + RA2)

```
exebox/prefix/__init__.py
exebox/prefix/layout.py            # 布局检测:pfx 真目录/自指链接/缺失
exebox/prefix/manager.py           # scaffold(只增不改)/check_version/is_managed
exebox/proton/runner.py            # build_environment/build_command(纯)+ execute
exebox/launch/__init__.py
exebox/launch/process.py           # subreaper(ctypes)/get_descendants(/proc)/信号树
exebox/launch/logger.py            # <箱>/logs/<ts>.launch.log
exebox/launch/launcher.py          # 编排 + dry_run()
exebox/cli.py                      # + launch 子命令(--dry-run/--env)
tests/unit/test_runner_build.py    # ★ 黄金环境/命令快照(三游戏)
tests/unit/test_process_tree.py    # 假 /proc 数据测树遍历
```

关键实现点:

- **黄金快照测试**(本里程碑的灵魂):`test_runner_build.py` 用 tmp_path 摆出
  假 proton/prefix/清单,断言 `build_environment`/`build_command` 的输出与
  start-{pvz,ra2,mo3}.sh 的语义逐字段等价 —— 实证配方从此受回归保护
- `build_environment` 分层(design §6.1):L1 继承 → L2 STEAM_COMPAT_* →
  L3 PATH 前插(path_append + proton/files/bin)→ L4 清单 env;
  **断言不含** WINEPREFIX/PROTONPATH/PROTON_VERB(负向断言也写进测试)
- `subreaper`:ctypes argtypes 精确;失败降级告警不炸;单独冒烟测试
- `execute`:Popen(start_new_session=True, cwd=manifest.game_dir,
  stdout/stderr→日志文件);SIGINT/SIGTERM→树遍历 kill
- 前台用 verb `run`(默认),阻塞至游戏退出

**完成判据**:
1. `exebox launch pvz --dry-run`:命令/env 全量打印,与 start-pvz.sh 语义一致
2. `exebox launch pvz` → 游戏窗口出现可玩;退出码如实;日志落盘
3. `exebox launch ra2` 同上(含空格路径无恙)
4. Ctrl-C:游戏整树退出,`pgrep` 无孤儿;另一游戏不受影响(用 PvZ+RA2 并行验证)
5. 单测绿,黄金快照三游戏全过

## 5. M3 施工图:`launch` 复杂局 + `install`

```
exebox/install/__init__.py
exebox/install/installer.py        # 编排:scaffold→跑安装器→steps→校验
exebox/install/steps.py            # shell/reg_add/copy/mkdir 执行器
exebox/cli.py                      # + install(向导 + --manifest/--import)
exebox/prefix/manager.py           # + 棘轮确认流/托管拒启
```

关键实现点:

- PATH 注入路径打通(MO3 的 mono 解析)—— M2 的 build_environment 已支持,
  此处验证真实链路:clientdx→Syringe→gamemd
- 向导 8 步(design §7.1):每步默认值可回车;专家可全改;最后打印清单全文再写
- `reg_add` step:经 ProtonRunner 走 `proton run reg add …/f [/reg:32]`
- 棘轮:非托管 + 交互 → y/N;`--bg`/管道 → 拒启 exit code 专用的

**完成判据**:
1. `exebox launch mo3` 全链通(肉眼验收 + syringe.log 有 hooks)
2. `exebox launch mo3 --dry-run` 可见 PATH 注入与 DLL 覆盖
3. 用 `~/Documents/codes/games/Plants_Vs_Zombies_*.exe` 真装一份到新箱:
   向导→安装器跑完→清单生成→launch 成功(US-1 端到端)
4. 棘轮演练:把清单 proton 改成 GE-Proton11-3 → 触发确认/拒启分支

## 6. M4 施工图:打磨

```
exebox/errors.py                   # 每个异常配"人话 + 建议动作"
exebox/cli.py                      # + --bg(+ ps 若排期)
README.md                          # 使用文档 + 三游戏实战示例
docs/                              # 设计文档行为规范同步终稿
```

- 全部错误路径走查:清单缺字段/引擎不存在/prefix 版本不符/exe 不存在 →
  一行人话,无 traceback
- `launch --bg`:detach + 落 pid 文件 + 日志路径打印
- 路径含空格/非 ASCII 清单 → 校验告警
- 三游戏最终回归 + 一轮真实使用体验

## 7. 测试策略总表

| 层 | 范围 | 工具 | 标记 |
|---|---|---|---|
| 单测 | models/loader/resolver/build_env/build_cmd/树遍历/棘轮 | pytest, tmp_path 假世界 | 默认 |
| 黄金快照 | 三游戏环境与命令 = 实证配方等价 | pytest(参数化) | 默认 |
| E2E | 真机启动三游戏/install 全流程/Ctrl-C 收割 | pytest subprocess | `@pytest.mark.e2e` |
| 手工 | 画面/音效/游戏内行为 | 人 | checklist 进 README |

## 8. 命令卡

```bash
uv add pyyaml rich typer            # 一次
uv add --dev pytest ruff            # 一次
uv sync                             # 每次拉取后
uv run exebox list                  # 开发期调用
uv run pytest                       # 单测
uv run pytest -m e2e                # 真机 E2E(需要三游戏在位)
uv run ruff check exebox tests      # lint
```

## 9. 风险与回退

| 风险 | 触发点 | 回退 |
|---|---|---|
| Proton Experimental 行为变化(xalia 层) | M2 E2E 偶发吞输出 | 日志文件为准;必要时清单可显式 verb 切换 |
| prctl 在某些内核/容器失败 | M2 冒烟 | 已设计降级路径(仅告警) |
| MO3 链路再出幺蛾子 | M3 | 清单字段已覆盖已知三坑;兜底走 umu 后端(备选,未排期) |
| 本机 Steam 更新 Proton | 随时 | 版本棘轮检测会拦;清单可钉住 compatibilitytools.d 的 GE/UMU |

## 10. 交付节奏

每个里程碑 = 1 个 git commit 序列(步骤级小提交)+ 里程碑级 tag(`m1`…`m4`)。
M1 预计半天内;M2 一天;M3 一天;M4 半天。停损点:任一里程碑判据不过,
不进入下一个。
