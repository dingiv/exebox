"""prefix 生命周期管理:脚手架(只增不改)、版本棘轮检查、托管检测。

铁律(design §6.4):已有的不动。scaffold 只创建缺失件,绝不转换布局、
绝不覆盖已有文件。pfx.lock 由 proton 自己的 filelock 创建(它带 O_CREAT,
只需根目录先存在 —— 2026-08-15 实测踩坑:根目录缺失才是秒退元凶)。

版本语义(实测,proton 脚本 line 44/49):
  每个 Proton 脚本内有 CURRENT_PREFIX_VERSION="11.0-100" 这样的常量,
  prefix/version 文件内容与之全等比较;不同则触发不可逆升级。
"""

import re
from pathlib import Path

from exebox.models import ProtonVersion
from exebox.prefix.layout import PrefixLayout, detect

_VERSION_RE = re.compile(r'^CURRENT_PREFIX_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)


def scaffold(prefix: Path) -> list[str]:
    """为全新/半成品 prefix 补齐 compatdata 结构(umu setup_pfx 移植)。

    返回实际执行的动作列表(供调用方展示);已有件一律跳过。
    """
    prefix = Path(prefix)
    actions: list[str] = []
    prefix.mkdir(parents=True, exist_ok=True)

    if detect(prefix) is PrefixLayout.MISSING:
        (prefix / "pfx").symlink_to(prefix, target_is_directory=True)
        actions.append("pfx -> .(自指符号链接)")

    for sub in ("shadercache", "gstreamer-1.0"):
        d = prefix / sub
        if not d.exists():
            d.mkdir(exist_ok=True)
            actions.append(f"{sub}/")

    tracked = prefix / "tracked_files"
    if not tracked.exists():
        tracked.touch()
        actions.append("tracked_files")

    _link_users(prefix)
    return actions


def _link_users(prefix: Path) -> None:
    """users/steamuser <-> unixuser 符号链接三态舞蹈(umu L102-118 移植)。

    仅在 drive_c/users 已存在(即 proton 完成过首次初始化)时有意义;
    全新 prefix 留给 proton 首跑自己建。
    """
    users_dir = prefix / "pfx" / "drive_c" / "users"
    if not users_dir.is_dir():
        return
    import getpass

    unix_user = getpass.getuser()
    steamuser = users_dir / "steamuser"
    unix_dir = users_dir / unix_user
    if steamuser.is_dir() and not unix_dir.exists():
        unix_dir.symlink_to("steamuser", target_is_directory=True)
    elif unix_dir.is_dir() and not steamuser.exists():
        steamuser.symlink_to(unix_user, target_is_directory=True)


def expected_prefix_version(proton: ProtonVersion) -> str | None:
    """从 proton 脚本中提取 CURRENT_PREFIX_VERSION。读不到返回 None。"""
    try:
        text = proton.proton_script.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = _VERSION_RE.search(text)
    return m.group(1) if m else None


def check_version(prefix: Path, proton: ProtonVersion) -> str:
    """版本棘轮检查。

    返回:
      no_prefix       prefix/version 不存在(全新,proton 会写入)
      match           版本一致,可安全启动
      upgrade_needed  不一致 —— proton 将执行不可逆升级(M3 起需确认)
      unknown         无法确定目标版本(脚本里没找到常量)—— 仅提示
    """
    current_file = Path(prefix) / "version"
    if not current_file.is_file():
        return "no_prefix"
    current = current_file.read_text(encoding="utf-8", errors="replace").strip()
    if not current:
        return "no_prefix"
    expected = expected_prefix_version(proton)
    if expected is None:
        return "unknown"
    return "match" if current == expected else "upgrade_needed"


def is_managed(prefix: Path) -> bool:
    """检测 prefix 是否被外部托管(Steam compatdata)—— 托管者只读。"""
    prefix = Path(prefix)
    if (prefix / "config_info").is_file():
        return True
    return "compatdata" in prefix.parts
