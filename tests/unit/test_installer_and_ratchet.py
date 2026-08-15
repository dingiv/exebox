"""Installer 编排 + 版本棘轮拦截测试(全 fake,零真实副作用)。"""

from pathlib import Path

import pytest

from exebox.config import Config
from exebox.errors import InstallError, PrefixVersionError
from exebox.install.installer import Installer
from exebox.launch.launcher import Launcher
from exebox.models import GameManifest
from exebox.proton.resolver import ProtonResolver


def make_fake_proton_dir(base: Path, version: str = "9.9-1") -> Path:
    d = base / "FakeProton"
    (d / "files" / "bin").mkdir(parents=True)
    (d / "proton").write_text(
        "#!/bin/bash\n"
        f'CURRENT_PREFIX_VERSION="{version}"\n'
        'echo "proton $1 $2"\n',
        encoding="utf-8",
    )
    (d / "proton").chmod(0o755)
    (d / "version").write_text(version, encoding="utf-8")
    return d


def build_world(tmp_path: Path, manifest_extra: dict | None = None,
                prefix_version: str | None = "9.9-1") -> tuple[Config, Launcher, Path]:
    make_fake_proton_dir(tmp_path / "steam" / "steamapps" / "common")
    config = Config(library_root=tmp_path / "lib", proton_home=tmp_path / "steam")
    launcher = Launcher(config, ProtonResolver(config.proton_home))
    box = config.library_root / "toy"
    game_dir = box / "game"
    game_dir.mkdir(parents=True)
    installer = tmp_path / "setup.exe"
    installer.write_text("fake", encoding="utf-8")
    manifest = {
        "name": "toy", "exe": "./game.exe",
        "proton": "FakeProton",
        "game_dir": str(game_dir),
        "prefix": str(box / "prefix"),
        "install": {
            "source": str(installer),
            "steps": [
                {"description": "安置 exe", "type": "copy",
                 "src": str(installer), "dst": str(game_dir / "game.exe")},
            ],
        },
    }
    manifest.update(manifest_extra or {})
    import yaml

    (box / "game.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8"
    )
    if prefix_version:
        (box / "prefix").mkdir(parents=True, exist_ok=True)
        (box / "prefix" / "version").write_text(prefix_version, encoding="utf-8")
    return config, launcher, box / "game.yaml"


def load_manifest_at(path: Path) -> GameManifest:
    from exebox.manifest.loader import load

    return load(path)


def test_installer_full_flow(tmp_path):
    _, launcher, mpath = build_world(tmp_path)
    manifest = load_manifest_at(mpath)
    Installer(launcher).install(manifest)
    assert manifest.exe.exists()  # copy step 把安装器复制成了 game.exe
    assert (manifest.box_path / "logs" / "install.log").is_file()
    # prefix 被脚手架补齐
    assert (manifest.prefix / "shadercache").is_dir()


def test_installer_requires_install_section(tmp_path):
    _, launcher, mpath = build_world(tmp_path, manifest_extra={
        "install": None,
    })
    import yaml

    raw = yaml.safe_load(mpath.read_text())
    del raw["install"]
    mpath.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(InstallError, match="install 段"):
        Installer(launcher).install(load_manifest_at(mpath))


def test_ratchet_blocks_without_confirm(tmp_path):
    # prefix 版本 1.0-0 ≠ fake proton 的 9.9-1 → 需要确认;confirm=None → 拒
    _, launcher, mpath = build_world(tmp_path, prefix_version="1.0-0")
    manifest = load_manifest_at(mpath)
    manifest.exe.write_text("x", encoding="utf-8")  # 让 plan 不至于因 exe 缺失分心
    with pytest.raises(PrefixVersionError, match="未获确认"):
        launcher.launch(manifest)


def test_ratchet_confirmed_proceeds(tmp_path):
    _, launcher, mpath = build_world(tmp_path, prefix_version="1.0-0")
    manifest = load_manifest_at(mpath)
    manifest.exe.write_text("x", encoding="utf-8")
    result = launcher.launch(manifest, confirm=lambda q: True)
    assert result.exit_code == 0  # fake proton echo 完就退
    assert any("棘轮升级已获确认" in n for n in launcher.notes)


def test_ratchet_match_launches_silently(tmp_path):
    _, launcher, mpath = build_world(tmp_path, prefix_version="9.9-1")
    manifest = load_manifest_at(mpath)
    manifest.exe.write_text("x", encoding="utf-8")
    result = launcher.launch(manifest)
    assert result.exit_code == 0
    assert not any("棘轮" in n for n in launcher.notes)


def test_ratchet_managed_prefix_hard_refusal(tmp_path):
    # 托管 prefix(路径含 compatdata)+ 版本不符 → 无条件拒启
    _, launcher, mpath = build_world(tmp_path, prefix_version="1.0-0")
    manifest = load_manifest_at(mpath)
    compatdata = tmp_path / "steam" / "steamapps" / "compatdata" / "123"
    compatdata.mkdir(parents=True)
    (compatdata / "version").write_text("1.0-0", encoding="utf-8")
    manifest.prefix = compatdata
    manifest.exe.write_text("x", encoding="utf-8")
    with pytest.raises(PrefixVersionError, match="Steam 托管"):
        launcher.launch(manifest, confirm=lambda q: True)  # 即使 confirm=True 也拒


def test_launcher_waits_for_detached_descendants(tmp_path):
    """引导器模式:被跟踪 exe 先退,真身子代还在 —— launch 必须等子代跑完。"""
    import os
    import time as _time

    from exebox.launch import process

    _, launcher, mpath = build_world(tmp_path)
    manifest = load_manifest_at(mpath)
    manifest.exe.write_text("x", encoding="utf-8")
    # fake proton:后台 sleep 3 后立即退出(模拟引导壳拉起真身)
    manifest_dir = tmp_path / "lib" / "toy"
    (manifest_dir / "prefix").mkdir(exist_ok=True)
    proton_dir = tmp_path / "steam" / "steamapps" / "common" / "FakeProton"
    proton_dir.joinpath("proton").write_text(
        '#!/bin/bash\nCURRENT_PREFIX_VERSION="9.9-1"\n(sleep 3 &)\nexit 0\n',
        encoding="utf-8",
    )
    process.last_signal = None
    t0 = _time.monotonic()
    result = launcher.launch(manifest)
    duration = _time.monotonic() - t0
    assert result.exit_code == 0
    assert duration >= 2.5, f"应在子代结束后才返回,实际 {duration:.1f}s"
    assert not process.descendants(os.getpid()), "返回时子代应已清空"


def test_installer_creates_missing_game_dir(tmp_path):
    """安装流程不要求 game_dir 预先存在(时序:装完才存在)。"""
    _, launcher, mpath = build_world(tmp_path)
    manifest = load_manifest_at(mpath)
    import shutil

    shutil.rmtree(manifest.game_dir)  # 模拟全新箱
    Installer(launcher).install(manifest)
    assert manifest.game_dir.is_dir()
    assert manifest.exe.exists()


def test_signaled_launcher_kills_stubborn_descendants(tmp_path):
    """被 SIGTERM 收割时,无视 TERM 的顽固子代要被 SIGKILL 清掉,launch 不得挂死。"""
    import subprocess
    import sys
    import time as _t

    build_world(tmp_path)
    mpath = tmp_path / "lib" / "toy" / "game.yaml"
    # fake proton:派生一个 trap 了 TERM 的顽固 sleep,然后自己退出(引导壳模式)
    proton_dir = tmp_path / "steam" / "steamapps" / "common" / "FakeProton"
    proton_dir.joinpath("proton").write_text(
        '#!/bin/bash\nCURRENT_PREFIX_VERSION="9.9-1"\n'
        "(bash -c \"trap '' TERM; sleep 60\") &\nexit 0\n",
        encoding="utf-8",
    )
    code = f"""
import os, signal, sys, time, threading
sys.path.insert(0, {str(Path.cwd())!r})
from exebox.config import Config
from exebox.launch.launcher import Launcher
from exebox.manifest.loader import load
from exebox.proton.resolver import ProtonResolver
m = load({str(mpath)!r})
m.exe.write_text('x')
# launch 安装信号处理器后,延迟自伤模拟外部收割
threading.Thread(
    target=lambda: (time.sleep(0.5), os.kill(os.getpid(), signal.SIGTERM)),
    daemon=True,
).start()
cfg = Config({str(tmp_path / 'lib')!r}, {str(tmp_path / 'steam')!r})
r = Launcher(cfg, ProtonResolver(cfg.proton_home)).launch(m)
print('RC', r.exit_code)
"""
    t0 = _t.monotonic()
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        timeout=20, check=False,
    )
    duration = _t.monotonic() - t0
    assert "RC -15" in out.stdout, out.stdout + out.stderr  # 如实报告被杀
    assert duration < 15, f"顽固子代导致挂等 {duration:.1f}s"
