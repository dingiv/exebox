# 事故复盘:自复制脚本炸弹(2026-08-15 晚)

> 项目外部事故,但档案于此:它污染了 exebox 的 E2E 验收环境近 90 分钟,
> 并在 git 历史里留下 8 条空转提交(已整理)。

## 时间线

| 时刻 | 事件 |
|---|---|
| 19:12 | 为 M3 收尾写 `/tmp/m3-wrap.sh`(git add/commit/tag + pkill 清场),**文件末尾误留一行 `chmod +x … && /tmp/m3-wrap.sh`(自执行)** —— 本该写在调用命令里,混进了 Write 内容 |
| 19:13 起 | 脚本每次运行:开头 `pkill -f [P]lantsVsZombies` → git 提交 → **重新执行自己** → 每 1-2 秒一代、指数级繁殖 |
| 19:13–19:44 | 数千副本轮转;每代开头的 pkill 持续谋杀所有新生游戏会话 —— 表现为"python 拉起的 proton 秒死、bash 黄金脚本幸存"的诡异分岔(实为繁殖周期采样偏差) |
| 期间误诊 | 陈旧 wineserver、会话 detach、工具沙箱、prefix 污染、subreaper/信号处理器(该 bug 是真的,但不是本案) |
| 19:44 | `strace -f -e signal` 抓到 `--- SIGTERM {si_pid=990740}` + 40ms 间隔 ps 快照抓拍 → 凶手 cmdline:`pkill -f [P]lantsVsZombies`,父链 = m3-wrap 自身 |
| 19:45 | 删源文件断繁殖 → 分批击杀 → exebox 全部复活 |

## 三条教训

1. **临时脚本绝不写自执行尾行**;"执行命令"与"文件内容"严格分离
2. pkill 系列罪行清单(本项目内三次踩坑 + 一次进化):
   - 复合命令含目标字面量 → 自匹配自杀
   - 监控 echo 文案含目标名 → pgrep 秒误报
   - 判活不排 `<defunct>` → 数尸体当幸存者(D3 复测差点误判)
   - **终极形态:写在会自我复制的脚本里 → 连环杀人机器**
3. 短命凶手的标准抓法(本案方法论,值得档案):
   ```
   strace -f -e trace=signal -o /tmp/s.txt <受害者启动器>   # 记录 si_pid
   grep -- "--- SIGTERM" /tmp/s.txt                          # 凶手指纹
   # 同时高频快照抓 cmdline:
   for i in $(seq 400); do ps --no-headers -eo pid,ppid,args >> watch.log; sleep 0.04; done
   ```

## 判活方法论升级(已用于 D3/D4 验收)

- 进程存活 ≠ 可用:必须 **排除 defunct** 且取**最新**实例(`ps | grep -v defunct`)
- CPU 判活:PopCap 菜单 >100%、对局内 40-90%、**报错框 <1%** —— 三态可辨
