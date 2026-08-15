from pathlib import Path

from exebox.config import Config
from exebox.models import GameManifest, InstallStep


def test_install_step_types():
    assert InstallStep.STEP_TYPES == ("shell", "reg_add", "copy", "mkdir")


def test_manifest_defaults():
    m = GameManifest(name="x", exe=Path("/g/x.exe"), proton="p", prefix=Path("/p"),
                     game_dir=Path("/g"))
    assert m.game_id == 0
    assert m.verb == "run"
    assert m.env == {}
    assert m.args == []
    assert m.install is None


def test_config_defaults(monkeypatch):
    monkeypatch.delenv("EXEBOX_HOME", raising=False)
    monkeypatch.delenv("EXEBOX_PROTON_HOME", raising=False)
    c = Config.from_env()
    assert c.library_root == Path.home() / "Games" / "exebox"
    assert c.proton_home == Path.home() / ".local" / "share" / "Steam"
    assert c.steam_install_path == c.proton_home


def test_config_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("EXEBOX_HOME", str(tmp_path / "lib"))
    monkeypatch.setenv("EXEBOX_PROTON_HOME", str(tmp_path / "steam"))
    c = Config.from_env()
    assert c.library_root == tmp_path / "lib"
    assert c.proton_home == tmp_path / "steam"
