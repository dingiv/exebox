"""doctor 检查器测试:健康/坏引擎/坏 exe/陈旧 pid/步骤缺 src。"""

from pathlib import Path

from exebox.doctor import diagnose, worst_status
from exebox.proton.resolver import ProtonResolver


def build(tmp_path: Path, manifest_overrides: dict | None = None):
    d = tmp_path / "steam" / "steamapps" / "common" / "FakeProton"
    (d / "files").mkdir(parents=True)
    (d / "proton").write_text('#!/bin/bash\nCURRENT_PREFIX_VERSION="9.9-1"\n', encoding="utf-8")
    (d / "proton").chmod(0o755)
    box = tmp_path / "lib" / "toy"
    game = box / "game"
    game.mkdir(parents=True)
    (game / "game.exe").write_text("x", encoding="utf-8")
    import yaml

    m = {
        "name": "toy", "exe": "./game.exe", "proton": "FakeProton",
        "game_dir": str(game), "prefix": str(box / "prefix"),
    }
    m.update(manifest_overrides or {})
    (box / "game.yaml").write_text(yaml.safe_dump(m), encoding="utf-8")
    from exebox.manifest.loader import load

    manifest = load(box / "game.yaml")
    resolver = ProtonResolver(tmp_path / "steam")
    return manifest, resolver


def test_healthy_box_all_ok(tmp_path):
    m, r = build(tmp_path)
    (m.prefix).mkdir(parents=True, exist_ok=True)
    (m.prefix / "version").write_text("9.9-1", encoding="utf-8")
    results = diagnose(m, r)
    assert worst_status(results) == "ok"
    names = {x.name for x in results}
    assert {"exe", "cwd", "proton", "prefix", "prefix-version", "box"} <= names


def test_bad_proton_name_fails_with_hint(tmp_path):
    m, r = build(tmp_path, {"proton": "Nope"})
    results = diagnose(m, r)
    pv = next(x for x in results if x.name == "proton")
    assert pv.status == "fail"
    assert "list --protons" in pv.suggestion


def test_missing_exe_fails(tmp_path):
    m, r = build(tmp_path)
    m.exe.unlink()
    results = diagnose(m, r)
    ex = next(x for x in results if x.name == "exe")
    assert ex.status == "fail"


def test_stale_pid_warns(tmp_path):
    m, r = build(tmp_path)
    (m.box_path / "run.pid").write_text("999999", encoding="utf-8")
    results = diagnose(m, r)
    running = next(x for x in results if x.name == "running")
    assert running.status == "warn" and "rm" in running.suggestion


def test_version_mismatch_warns(tmp_path):
    m, r = build(tmp_path)
    m.prefix.mkdir(parents=True)
    (m.prefix / "version").write_text("1.0-0", encoding="utf-8")
    results = diagnose(m, r)
    v = next(x for x in results if x.name == "prefix-version")
    assert v.status == "warn" and "不可逆" in v.detail
