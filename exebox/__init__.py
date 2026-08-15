"""exebox —— wine/proton 的前端。

公共 API(core 即库,CLI/GUI 共用):
  Config / GameManifest / ProtonVersion …  数据模型
  manifest.loader.load                     清单加载
  proton.resolver.ProtonResolver           引擎发现
  registry.store.RegistryStore             库扫描与缓存
"""

__version__ = "0.1.0"

from exebox.config import Config
from exebox.errors import ExeboxError
from exebox.manifest.loader import MANIFEST_FILENAME, load, load_box
from exebox.models import (
    GameEntry,
    GameManifest,
    InstallConfig,
    InstallStep,
    LaunchResult,
    ProtonVersion,
)
from exebox.proton.resolver import DEFAULT_PROTON_NAME, ProtonResolver
from exebox.registry.store import RegistryStore

__all__ = [
    "DEFAULT_PROTON_NAME",
    "MANIFEST_FILENAME",
    "Config",
    "ExeboxError",
    "GameEntry",
    "GameManifest",
    "InstallConfig",
    "InstallStep",
    "LaunchResult",
    "ProtonResolver",
    "ProtonVersion",
    "RegistryStore",
    "__version__",
    "load",
    "load_box",
]
