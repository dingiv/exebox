"""ProtonRunner:环境组装与命令构造(纯函数,零副作用)。

环境分层(design §6.1,证据忠实最小集):
  L1 继承当前环境
  L2 STEAM_COMPAT_DATA_PATH / STEAM_COMPAT_CLIENT_INSTALL_PATH
     (+ SteamAppId/SteamGameId,仅 game_id 非零时)
  L3 PATH 前插:path_append 逐项 + <proton>/files/bin
  L4 清单 env + dll_overrides 展开 + 命令行 --env 覆盖(最高优先级)

刻意不设(实证:三张验证配方均不需要;直调 proton 而非 umu):
  WINEPREFIX / PROTONPATH / PROTON_VERB
"""

import os
from dataclasses import dataclass
from pathlib import Path

from exebox.models import GameManifest, ProtonVersion

FORBIDDEN_ENV_KEYS = ("WINEPREFIX", "PROTONPATH", "PROTON_VERB")


@dataclass(frozen=True)
class LaunchPlan:
    """一次启动的完整计划(dry-run 的输出物,纯数据)。"""

    command: list[str]
    env: dict[str, str]
    cwd: Path
    log_path: Path
    proton: ProtonVersion


class ProtonRunner:
    def __init__(self, proton: ProtonVersion, steam_install_path: Path):
        self._proton = proton
        self._steam_install = Path(steam_install_path)

    @property
    def proton(self) -> ProtonVersion:
        return self._proton

    def build_environment(
        self,
        manifest: GameManifest,
        extra_env: dict[str, str] | None = None,
        base_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """组装启动环境。base_env 供测试注入(None 则用 os.environ)。"""
        env = dict(base_env if base_env is not None else os.environ)

        # L2
        env["STEAM_COMPAT_DATA_PATH"] = str(manifest.prefix)
        env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] = str(self._steam_install)
        if manifest.game_id:
            env["SteamAppId"] = str(manifest.game_id)
            env["SteamGameId"] = str(manifest.game_id)

        # L3:PATH 前插(先 path_append,后 proton bin)
        prepends = [str(p) for p in manifest.path_append]
        prepends.append(str(self._proton.path / "files" / "bin"))
        old_path = env.get("PATH", "")
        env["PATH"] = ":".join(prepends + ([old_path] if old_path else []))

        # L4:清单 env > dll_overrides 简写 > --env 覆盖
        merged: dict[str, str] = dict(manifest.env)
        if manifest.dll_overrides and "WINEDLLOVERRIDES" not in merged:
            merged["WINEDLLOVERRIDES"] = manifest.dll_overrides
        merged.update(extra_env or {})
        env.update(merged)
        return env

    def build_command(self, manifest: GameManifest) -> list[str]:
        """[proton 脚本, verb, exe, *args] —— 清单里是什么就是什么。"""
        return [
            str(self._proton.proton_script),
            manifest.verb,
            str(manifest.exe),
            *manifest.args,
        ]
