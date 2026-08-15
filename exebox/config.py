"""全局配置:库根目录与 Proton 主目录的发现。

环境变量覆盖:
  EXEBOX_HOME          库根目录(默认 ~/Games/exebox)
  EXEBOX_PROTON_HOME   Steam 数据目录(默认 ~/.local/share/Steam)
"""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LIBRARY_ROOT = Path.home() / "Games" / "exebox"
DEFAULT_PROTON_HOME = Path.home() / ".local" / "share" / "Steam"


@dataclass(frozen=True)
class Config:
    library_root: Path
    proton_home: Path

    @property
    def steam_install_path(self) -> Path:
        """STEAM_COMPAT_CLIENT_INSTALL_PATH 的取值(与 proton_home 同目录)。"""
        return self.proton_home

    @classmethod
    def from_env(cls) -> "Config":
        library_root = Path(
            os.environ.get("EXEBOX_HOME", str(DEFAULT_LIBRARY_ROOT))
        ).expanduser()
        proton_home = Path(
            os.environ.get("EXEBOX_PROTON_HOME", str(DEFAULT_PROTON_HOME))
        ).expanduser()
        return cls(library_root=library_root, proton_home=proton_home)
