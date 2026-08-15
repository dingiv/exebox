"""进程树治理(umu_run.py:693-747 移植,design §6.3)。

三件套:
  1. prctl(PR_SET_CHILD_SUBREAPER) —— 自封子收割者,孤儿归我
  2. /proc PPid 扫描建树(可注入假 /proc 供测试)
  3. SIGINT/SIGTERM → 遍历自己的树逐个转发(永不 pkill wineserver)
"""

import ctypes
import os
import signal
from pathlib import Path

PR_SET_CHILD_SUBREAPER = 36  # Linux 3.4+

# 最近一次转发给子树的信号(供上层如实报告"被信号杀死")
last_signal: int | None = None


def setup_subreaper() -> bool:
    """设置本进程为子收割者。失败返回 False(降级仅告警,不致命)。

    argtypes 必须精确:错配 = 静默内存踩踏(实测风险,umu 同款防御)。
    """
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
    except OSError:
        return False
    prctl = libc.prctl
    prctl.restype = ctypes.c_int
    prctl.argtypes = [
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
    ]
    ret = prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0)
    return ret == 0


def descendants_from_proc(proc_root: Path, root_pid: int) -> set[int]:
    """扫描 <proc_root>/<pid>/status 的 PPid 字段,返回 root_pid 的全部后代。

    proc_root 可注入(测试用假树);root_pid 自身不在结果里。
    僵尸(State=Z)视为已死 —— 它们只是还没被收尸,/proc 里仍占着 PPid,
    若当活人等会死循环(实测教训:subreaper 收养的孤儿无人 wait 即成永尸)。
    竞态容忍:status 消失即跳过。
    """
    parents: dict[int, int] = {}
    if not proc_root.is_dir():
        return set()
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        status = entry / "status"
        try:
            ppid: int | None = None
            for line in status.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("State:") and line.split()[1].startswith("Z"):
                    ppid = None  # 僵尸:不算活人
                    break
                if line.startswith("PPid:"):
                    ppid = int(line.split()[1])
                    break
            if ppid is not None:
                parents[int(entry.name)] = ppid
        except (OSError, ValueError, IndexError):
            continue
    # BFS:父 → 子
    children: dict[int, list[int]] = {}
    for pid, ppid in parents.items():
        children.setdefault(ppid, []).append(pid)
    out: set[int] = set()
    frontier = [root_pid]
    while frontier:
        pid = frontier.pop()
        for child in children.get(pid, []):
            if child not in out:
                out.add(child)
                frontier.append(child)
    return out


def descendants(root_pid: int) -> set[int]:
    return descendants_from_proc(Path("/proc"), root_pid)


def kill_tree(root_pid: int, sig: int) -> int:
    """向 root_pid 及其全部后代发送信号,返回成功投递数。"""
    targets = descendants(root_pid) | {root_pid}
    sent = 0
    for pid in targets:
        try:
            os.kill(pid, sig)
            sent += 1
        except (ProcessLookupError, PermissionError):
            continue
    return sent


def install_signal_handlers() -> None:
    """注册 SIGINT/SIGTERM 转发器:信号到达 → 收割"自己的全部后代"。

    目标是 os.getpid() 的后代而非 proton 脚本的子树 —— 因为 xalia 会话层
    会 double-fork 游戏进程;但我们设了 subreaper,被遗弃的进程会过继给
    exebox 本身,所以"我的后代"才是完备集合(实测教训 2026-08-15)。
    """

    def _forward(signum: int, _frame) -> None:
        global last_signal
        last_signal = signum
        kill_descendants_of_self(signum)

    signal.signal(signal.SIGINT, _forward)
    signal.signal(signal.SIGTERM, _forward)


def kill_descendants_of_self(sig: int) -> int:
    """向本进程的全部后代(不含自身)发送信号,返回投递数。"""
    targets = descendants(os.getpid())
    sent = 0
    for pid in targets:
        try:
            os.kill(pid, sig)
            sent += 1
        except (ProcessLookupError, PermissionError):
            continue
    return sent


def prefix_session_pids(data_path: str, proc_root: Path | None = None) -> set[int]:
    """扫描 /proc/*/environ,返回携带 STEAM_COMPAT_DATA_PATH=<data_path> 的活进程。

    用途:引导器型程序(MO3)的子树会被 xalia 移出我方进程族谱,
    descendants() 看不到 —— 按 prefix 环境变量关联才能等到真身结束(等待保真)。
    僵尸不算活;environ 不可读(hidepid 等)时该进程被跳过,静默降级。
    """
    root = proc_root or Path("/proc")
    needle = f"STEAM_COMPAT_DATA_PATH={data_path}\0".encode()
    out: set[int] = set()
    if not root.is_dir():
        return out
    for entry in root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            environ = (entry / "environ").read_bytes()
        except OSError:
            continue
        if needle not in environ:
            continue
        try:
            status = (entry / "status").read_text(encoding="utf-8", errors="replace")
        except OSError:
            status = ""
        if "\nState:\tZ" in status or status.startswith("State:\tZ"):
            continue  # 僵尸不算活
        out.add(int(entry.name))
    return out
