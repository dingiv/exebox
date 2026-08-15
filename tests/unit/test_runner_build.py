"""黄金快照测试:三张实证配方(start-{pvz,ra2,mo3}.sh)的语义固化。

谁改坏了 build_environment / build_command,这里立刻红。
含负向断言:环境里禁止出现 WINEPREFIX / PROTONPATH / PROTON_VERB。
"""

from pathlib import Path

import pytest

from exebox.models import GameManifest, ProtonVersion
from exebox.proton.runner import FORBIDDEN_ENV_KEYS, ProtonRunner

BASE_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/home/div"}

STEAM = Path("/home/div/.local/share/Steam")


def make_proton(tmp_path: Path) -> ProtonVersion:
    d = tmp_path / "Proton - Experimental"
    d.mkdir()
    (d / "proton").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    return ProtonVersion(name=d.name, path=d, proton_script=d / "proton",
                         version_str="exp", source="steam")


@pytest.fixture()
def proton(tmp_path):
    return make_proton(tmp_path)


@pytest.fixture()
def runner(proton):
    return ProtonRunner(proton, STEAM)


# ---- PvZ 配方:start-pvz.sh 语义 ----

def test_golden_pvz(runner, proton):
    m = GameManifest(
        name="pvz", exe=Path("/games/pvz/PlantsVsZombies.exe"), proton="x",
        prefix=Path("/games/pvz-exp-prefix"), game_dir=Path("/games/pvz"),
    )
    env = runner.build_environment(m, base_env=BASE_ENV)
    cmd = runner.build_command(m)
    assert cmd == [str(proton.proton_script), "run", "/games/pvz/PlantsVsZombies.exe"]
    assert env["STEAM_COMPAT_DATA_PATH"] == "/games/pvz-exp-prefix"
    assert env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] == str(STEAM)
    assert env["PATH"].startswith(str(proton.path / "files" / "bin") + ":/usr/bin:/bin")
    assert "SteamAppId" not in env  # game_id=0 → 不伪造 Steam 身份
    for k in FORBIDDEN_ENV_KEYS:
        assert k not in env


# ---- RA2 配方:空格路径 + Steam compatdata ----

def test_golden_ra2(runner, proton):
    gdir = Path("/steam/common/Command & Conquer Red Alert II")
    m = GameManifest(
        name="ra2", exe=gdir / "gamemd.exe", proton="x",
        prefix=Path("/steam/compatdata/2229850"), game_dir=gdir,
        game_id=2229850,
    )
    env = runner.build_environment(m, base_env=BASE_ENV)
    cmd = runner.build_command(m)
    assert cmd == [str(proton.proton_script), "run", str(gdir / "gamemd.exe")]
    assert env["STEAM_COMPAT_DATA_PATH"] == "/steam/compatdata/2229850"
    assert env["SteamAppId"] == "2229850"  # 非零才注入
    assert env["SteamGameId"] == "2229850"
    for k in FORBIDDEN_ENV_KEYS:
        assert k not in env


# ---- MO3 配方:PATH 注入 + DLL 覆盖 + args ----

def test_golden_mo3(runner, proton):
    gdir = Path("/games/mo3/drive_c/Program Files (x86)/Mental Omega")
    m = GameManifest(
        name="mo3", exe=gdir / "MentalOmegaClient.exe", proton="x",
        prefix=Path("/games/mo3"), game_dir=gdir,
        dll_overrides="ddraw=n,b",
        path_append=[gdir],
        args=["-SPAWN"],
        verb="run",
    )
    env = runner.build_environment(m, base_env=BASE_ENV)
    cmd = runner.build_command(m)
    assert cmd == [
        str(proton.proton_script), "run",
        str(gdir / "MentalOmegaClient.exe"), "-SPAWN",
    ]
    # PATH 顺序:游戏目录 → proton bin → 原 PATH
    p = env["PATH"].split(":")
    assert p[0] == str(gdir)
    assert p[1] == str(proton.path / "files" / "bin")
    assert env["WINEDLLOVERRIDES"] == "ddraw=n,b"
    for k in FORBIDDEN_ENV_KEYS:
        assert k not in env


# ---- 分层与覆盖语义 ----

def test_env_layers_priority(runner):
    m = GameManifest(
        name="x", exe=Path("/g/x.exe"), proton="x",
        prefix=Path("/p"), game_dir=Path("/g"),
        env={"FOO": "manifest", "BAR": "manifest"},
    )
    env = runner.build_environment(m, extra_env={"BAR": "cli"}, base_env=BASE_ENV)
    assert env["FOO"] == "manifest"  # 清单生效
    assert env["BAR"] == "cli"  # --env 覆盖清单


def test_explicit_env_wins_over_dll_shorthand(runner):
    m = GameManifest(
        name="x", exe=Path("/g/x.exe"), proton="x",
        prefix=Path("/p"), game_dir=Path("/g"),
        env={"WINEDLLOVERRIDES": "from-env"},
        dll_overrides="from-shorthand",
    )
    env = runner.build_environment(m, base_env=BASE_ENV)
    assert env["WINEDLLOVERRIDES"] == "from-env"


def test_command_passes_args_verbatim(runner, proton):
    m = GameManifest(
        name="x", exe=Path("/g/x.exe"), proton="x",
        prefix=Path("/p"), game_dir=Path("/g"),
        args=["-SPAWN", "-CD", "-LOG"], verb="waitforexitandrun",
    )
    assert runner.build_command(m) == [
        str(proton.proton_script), "waitforexitandrun", "/g/x.exe",
        "-SPAWN", "-CD", "-LOG",
    ]
