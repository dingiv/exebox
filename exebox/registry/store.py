"""游戏注册表:扫描为真相,registry.json 仅为缓存(design §4)。

约定:
- games() 总是扫 <library_root>/*/game.yaml —— manifest 是唯一真相
- sync() 把扫描结果写入 registry.json(hash 记录清单内容指纹)
- registry.json 损坏/缺失不影响任何功能(重建即可)
"""

import hashlib
import json
from pathlib import Path

from exebox.config import Config
from exebox.errors import ExeboxError, RegistryError
from exebox.manifest.loader import MANIFEST_FILENAME, load
from exebox.models import GameEntry, GameManifest

REGISTRY_FILENAME = "registry.json"


def manifest_hash(manifest_path: Path) -> str:
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()[:16]


class RegistryStore:
    def __init__(self, library_root: Path | None = None):
        self._root = Path(library_root) if library_root else Config.from_env().library_root
        self._registry_path = self._root / REGISTRY_FILENAME

    @property
    def library_root(self) -> Path:
        return self._root

    def games(self) -> dict[str, GameManifest]:
        """扫描库根,返回 {slug: GameManifest}。坏清单跳过并记录在 failures()。"""
        self._failures: list[tuple[Path, str]] = []
        games: dict[str, GameManifest] = {}
        if not self._root.is_dir():
            return games
        for box in sorted(self._root.iterdir()):
            manifest_path = box / MANIFEST_FILENAME
            if not (box.is_dir() and manifest_path.is_file()):
                continue
            try:
                m = load(manifest_path)
            except ExeboxError as e:  # 坏清单不拖垮整个 list
                self._failures.append((manifest_path, str(e)))
                continue
            games[m.slug] = m
        return games

    def failures(self) -> list[tuple[Path, str]]:
        """最近一次 games() 遇到的坏清单(路径, 错误)。"""
        return getattr(self, "_failures", [])

    def entries(self) -> list[GameEntry]:
        return [
            GameEntry(
                slug=m.slug,
                name=m.name,
                box_path=m.box_path,
                manifest_path=m.box_path / MANIFEST_FILENAME,
                manifest_hash=manifest_hash(m.box_path / MANIFEST_FILENAME),
            )
            for m in self.games().values()
        ]

    def sync(self) -> int:
        """把扫描结果写入 registry.json 缓存,返回条目数。"""
        entries = self.entries()
        payload = {
            "version": 1,
            "entries": [
                {
                    "slug": e.slug,
                    "name": e.name,
                    "box_path": str(e.box_path),
                    "manifest_path": str(e.manifest_path),
                    "manifest_hash": e.manifest_hash,
                }
                for e in entries
            ],
        }
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            self._registry_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as e:
            raise RegistryError(f"写 registry.json 失败: {e}") from e
        return len(entries)
