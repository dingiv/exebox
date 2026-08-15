"""prefix 布局检测(design §6.4)。

三种现存布局,只识别不转换:
  REAL_DIR     pfx 是真实目录(Steam compatdata / 直调 proton 风格)
  SELF_SYMLINK pfx 是自指符号链接(umu/Lutris 风格,pfx -> .)
  MISSING      pfx 不存在(全新 prefix)
"""

from enum import Enum
from pathlib import Path


class PrefixLayout(Enum):
    REAL_DIR = "real_dir"
    SELF_SYMLINK = "self_symlink"
    MISSING = "missing"


def detect(prefix: Path) -> PrefixLayout:
    pfx = Path(prefix) / "pfx"
    if pfx.is_symlink():
        return PrefixLayout.SELF_SYMLINK
    if pfx.is_dir():
        return PrefixLayout.REAL_DIR
    return PrefixLayout.MISSING
