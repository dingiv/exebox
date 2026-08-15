"""核心数据模型(纯数据,无 IO)。

对应 design §5.2。路径字段一律为解析后的绝对 Path。
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ProtonVersion:
    """本机发现的一个 Proton 安装。"""

    name: str  # 目录名,如 "Proton - Experimental"、"GE-Proton11-3"
    path: Path  # Proton 根目录(proton 脚本的父目录)
    proton_script: Path  # <path>/proton
    version_str: str  # version 文件内容(首行),读不到为 ""
    source: str  # "steam" | "compatibilitytools"


@dataclass
class InstallStep:
    """安装期的一个步骤(顺序执行,失败即停)。

    type 决定哪些字段有效:
      shell   -> command: list[str](经 ProtonRunner 在同 prefix 下执行)
      reg_add -> key/value/value_type/reg_hive/reg_arch
      copy    -> src/dst
      mkdir   -> dst
    """

    STEP_TYPES = ("shell", "reg_add", "copy", "mkdir")

    description: str
    type: str
    command: list[str] | None = None
    key: str | None = None
    value: str | None = None
    value_type: str | None = None  # "SZ" | "DWORD"
    reg_hive: str | None = None  # "HKLM" | "HKCU"
    reg_arch: str | None = None  # "32" | "64"
    src: Path | None = None
    dst: Path | None = None


@dataclass
class InstallConfig:
    """清单的 install 段(仅 install 命令消费,launch 忽略)。"""

    source: Path
    steps: list[InstallStep] = field(default_factory=list)


@dataclass
class GameManifest:
    """一份 game.yaml 的解析结果(唯一配置真相)。"""

    name: str
    exe: Path  # 绝对路径
    proton: str  # 引擎名称(未解析,ProtonResolver 负责)
    prefix: Path  # compatdata 根,绝对路径
    game_dir: Path  # 启动 cwd,绝对路径
    env: dict[str, str] = field(default_factory=dict)
    dll_overrides: str = ""
    args: list[str] = field(default_factory=list)
    game_id: int = 0  # 0 = 完全不设 SteamAppId
    path_append: list[Path] = field(default_factory=list)
    verb: str = "run"
    notes: str = ""
    install: InstallConfig | None = None
    # 以下为加载时推导,不来自 YAML
    box_path: Path = Path()  # 清单所在目录
    slug: str = ""  # 箱目录名(稳定 ID)


@dataclass
class GameEntry:
    """registry 中的一个游戏条目(manifest 的缓存索引)。"""

    slug: str
    name: str
    box_path: Path
    manifest_path: Path
    manifest_hash: str  # game.yaml 内容的 sha256 前 16 位


@dataclass
class LaunchResult:
    """一次启动的结果(M2 实现,先定型)。"""

    exit_code: int
    pid: int
    duration_seconds: float
    log_path: Path | None = None
