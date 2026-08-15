"""启动日志:每次启动一份,落在箱内 logs/ 目录。"""

from datetime import datetime
from pathlib import Path


def new_log_path(box_path: Path) -> Path:
    """计算本次启动的日志路径(不创建任何东西,dry-run 安全)。"""
    ts = datetime.now().astimezone().strftime("%Y-%m-%dT%H-%M-%S")
    return Path(box_path) / "logs" / f"{ts}.launch.log"


def open_launch_log(path: Path):
    """创建目录并打开日志文件(调用方负责 close)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    return open(path, "w", encoding="utf-8", errors="replace")
