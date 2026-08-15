"""Proton 发现与名称解析(design §5.1)。

扫描两个位置,凡目录内存在可执行 proton 脚本即算一个版本:
  1. <proton_home>/steamapps/common/<名称>/proton     (官方,Steam 维护)
  2. <proton_home>/compatibilitytools.d/<名称>/proton  (GE/UMU 等手动安装)

名称解析:精确名(先 compatibilitytools.d)→ 精确名(steamapps)→ 模糊匹配
(双方都去掉非字母数字后小写比较,如 "proton-experimental" ≈ "Proton - Experimental")。
"""

from pathlib import Path

from exebox.config import Config
from exebox.errors import NoProtonFoundError, ProtonNotFoundError
from exebox.models import ProtonVersion

DEFAULT_PROTON_NAME = "Proton - Experimental"


class ProtonResolver:
    def __init__(self, proton_home: Path | None = None):
        self._proton_home = Path(proton_home) if proton_home else Config.from_env().proton_home

    def list_available(self) -> list[ProtonVersion]:
        """列出本机全部 Proton,compatibilitytools.d 优先排前。"""
        found: list[ProtonVersion] = []
        for source, sub in (
            ("compatibilitytools", "compatibilitytools.d"),
            ("steam", "steamapps/common"),
        ):
            base = self._proton_home / sub
            if not base.is_dir():
                continue
            for entry in sorted(base.iterdir()):
                if not entry.is_dir():
                    continue
                script = entry / "proton"
                if not script.is_file():
                    continue
                found.append(
                    ProtonVersion(
                        name=entry.name,
                        path=entry,
                        proton_script=script,
                        version_str=_read_version(entry),
                        source=source,
                    )
                )
        if not found:
            raise NoProtonFoundError(
                f"在 {self._proton_home} 下未发现任何 Proton"
                f"(扫描了 compatibilitytools.d/ 与 steamapps/common/;"
                f"可用 EXEBOX_PROTON_HOME 指定 Steam 数据目录)"
            )
        return found

    def resolve(self, name: str | None = None) -> ProtonVersion:
        """把清单里的 proton 名称解析为本机安装。name 为 None 用默认。"""
        target = name or DEFAULT_PROTON_NAME
        available = self.list_available()
        # 1/2: 精确名(list_available 已保证 compat 在前)
        for pv in available:
            if pv.name == target:
                return pv
        # 3: 模糊匹配
        norm = _normalize(target)
        for pv in available:
            if _normalize(pv.name) == norm:
                return pv
        raise ProtonNotFoundError(
            f"找不到 Proton '{target}'。本机可用: "
            + ", ".join(pv.name for pv in available)
        )


def _read_version(proton_dir: Path) -> str:
    vfile = proton_dir / "version"
    if not vfile.is_file():
        return ""
    lines = [
        ln.strip()
        for ln in vfile.read_text(encoding="utf-8", errors="replace").splitlines()
        if ln.strip()
    ]
    if not lines:
        return ""
    # Proton 的 version 行格式为 "<构建时间戳> <可读版本>",剥掉时间戳
    parts = lines[0].split(maxsplit=1)
    if parts and parts[0].isdigit() and len(parts) > 1:
        return parts[1]
    return lines[0]


def _normalize(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())
