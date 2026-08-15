from pathlib import Path

import pytest

from exebox.errors import ManifestError
from exebox.manifest.loader import load


def write(tmp_path: Path, data: dict | str, name: str = "game.yaml") -> Path:
    p = tmp_path / name
    if isinstance(data, str):
        p.write_text(data, encoding="utf-8")
    else:
        import yaml
        p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def test_full_manifest(tmp_path):
    write(tmp_path, {
        "name": "玩具", "exe": "./run.exe", "proton": "GE-Proton11-3",
        "prefix": "./pfx", "game_dir": "/games/toy",
        "env": {"FOO": "bar"}, "dll_overrides": "ddraw=n,b",
        "args": ["-a", "-b"], "game_id": 123,
        "path_append": ["/x/y", "rel/dir"], "verb": "waitforexitandrun",
        "notes": "n",
    })
    m = load(tmp_path / "game.yaml")
    assert m.name == "玩具"
    assert m.exe == Path("/games/toy/run.exe")
    assert m.proton == "GE-Proton11-3"
    assert m.prefix == tmp_path / "pfx"
    assert m.game_dir == Path("/games/toy")
    assert m.env == {"FOO": "bar"}
    assert m.dll_overrides == "ddraw=n,b"
    assert m.args == ["-a", "-b"]
    assert m.game_id == 123
    assert m.path_append == [Path("/x/y"), tmp_path / "rel/dir"]
    assert m.verb == "waitforexitandrun"
    assert m.slug == tmp_path.name
    assert m.box_path == tmp_path


def test_minimal_manifest_absolute_exe(tmp_path):
    write(tmp_path, {"exe": "/games/toy/run.exe"})
    m = load(tmp_path / "game.yaml")
    assert m.exe == Path("/games/toy/run.exe")
    assert m.game_dir == Path("/games/toy")  # 默认 = exe 所在目录
    assert m.proton == "Proton - Experimental"
    assert m.prefix == tmp_path / "prefix"
    assert m.game_id == 0
    assert m.verb == "run"
    assert m.name == tmp_path.name  # 默认 = 目录名


def test_relative_exe_requires_game_dir(tmp_path):
    write(tmp_path, {"exe": "./run.exe"})
    with pytest.raises(ManifestError, match="game_dir"):
        load(tmp_path / "game.yaml")


def test_missing_exe_field(tmp_path):
    write(tmp_path, {"name": "x"})
    with pytest.raises(ManifestError, match="exe"):
        load(tmp_path / "game.yaml")


def test_unknown_root_field_rejected(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "envv": {}})
    with pytest.raises(ManifestError, match="未知字段.*envv"):
        load(tmp_path / "game.yaml")


def test_bad_args_type_rejected(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "args": "not-a-list"})
    with pytest.raises(ManifestError, match="args"):
        load(tmp_path / "game.yaml")


def test_bad_game_id_rejected(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "game_id": -1})
    with pytest.raises(ManifestError, match="game_id"):
        load(tmp_path / "game.yaml")


def test_env_values_coerced_to_str(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "env": {"N": 5, "B": True}})
    m = load(tmp_path / "game.yaml")
    assert m.env == {"N": "5", "B": "True"}


def test_install_steps(tmp_path):
    write(tmp_path, {
        "exe": "/a/b.exe",
        "install": {
            "source": "/setup.exe",
            "steps": [
                {"description": "静默装", "type": "shell",
                 "command": ["/setup.exe", "/S"]},
                {"description": "注册表", "type": "reg_add",
                 "key": r"HKLM\Software\X", "value": "1",
                 "value_type": "DWORD", "reg_arch": "32"},
                {"type": "copy", "src": "a.bin", "dst": "/tmp/b.bin"},
                {"type": "mkdir", "dst": "data/dir"},
            ],
        },
    })
    m = load(tmp_path / "game.yaml")
    assert m.install is not None
    assert m.install.source == Path("/setup.exe")
    kinds = [s.type for s in m.install.steps]
    assert kinds == ["shell", "reg_add", "copy", "mkdir"]
    assert m.install.steps[1].reg_arch == "32"
    assert m.install.steps[2].src == tmp_path / "a.bin"  # 相对 = 箱根


def test_install_unknown_step_type_rejected(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "install": {
        "source": "/s", "steps": [{"type": "winetricks"}]}})
    with pytest.raises(ManifestError, match="winetricks"):
        load(tmp_path / "game.yaml")


def test_install_unknown_field_rejected(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "install": {
        "source": "/s", "steps": [{"type": "mkdir", "dst": "/d", "zzz": 1}]}})
    with pytest.raises(ManifestError, match="未知字段.*zzz"):
        load(tmp_path / "game.yaml")


def test_install_requires_source(tmp_path):
    write(tmp_path, {"exe": "/a/b.exe", "install": {"steps": []}})
    with pytest.raises(ManifestError, match="source"):
        load(tmp_path / "game.yaml")


def test_broken_yaml_rejected(tmp_path):
    write(tmp_path, "exe: [unclosed")
    with pytest.raises(ManifestError, match="YAML"):
        load(tmp_path / "game.yaml")


def test_non_mapping_rejected(tmp_path):
    write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ManifestError, match="映射"):
        load(tmp_path / "game.yaml")
