"""prefix 生命周期操作:reset(重建假电脑)与 shell 所需的环境就绪。

reset 是破坏性操作 —— 三道闸:
  1. 托管 prefix(steamapps/compatdata)拒绝
  2. 该箱正在运行(run.pid 活着)拒绝
  3. CLI 层确认提示(--yes 供非交互)
"""

import os
import shutil
from pathlib import Path

from exebox.errors import PrefixError
from exebox.prefix import manager


def reset(prefix: Path, box_path: Path) -> list[str]:
    """删除 prefix 全部内容并重建脚手架。返回 scaffold 动作列表。"""
    prefix = Path(prefix)
    if manager.is_managed(prefix):
        raise PrefixError(
            f"prefix 由 Steam 托管({prefix}),exebox 不代管它的生命周期"
            "(要重置请通过 Steam 删除兼容性数据)"
        )
    pid_file = Path(box_path) / "run.pid"
    if pid_file.is_file():
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if os.path.isdir(f"/proc/{pid}"):
            raise PrefixError(
                f"该箱正在运行(pid={pid}),先 exebox ps 确认并 kill 后再 reset"
            )
    if prefix.is_symlink() or prefix.is_file():
        raise PrefixError(f"prefix 路径异常(非目录): {prefix}")
    if prefix.exists():
        shutil.rmtree(prefix)
    return manager.scaffold(prefix)
