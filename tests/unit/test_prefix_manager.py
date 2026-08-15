from pathlib import Path

from exebox.models import ProtonVersion
from exebox.prefix import manager
from exebox.prefix.layout import PrefixLayout, detect


def make_proton(base: Path, version_line: str = 'CURRENT_PREFIX_VERSION="11.0-100"') -> ProtonVersion:
    d = base / "FakeProton"
    d.mkdir(parents=True)
    (d / "proton").write_text(f"#!/usr/bin/env python3\n{version_line}\n", encoding="utf-8")
    return ProtonVersion(
        name=d.name, path=d, proton_script=d / "proton",
        version_str="x", source="compatibilitytools",
    )


def test_scaffold_creates_umu_layout(tmp_path):
    prefix = tmp_path / "box" / "prefix"
    actions = manager.scaffold(prefix)
    assert (prefix / "pfx").is_symlink()
    assert Path(prefix / "pfx").resolve() == prefix.resolve()
    assert (prefix / "shadercache").is_dir()
    assert (prefix / "gstreamer-1.0").is_dir()
    assert (prefix / "tracked_files").is_file()
    assert len(actions) == 4


def test_scaffold_idempotent(tmp_path):
    prefix = tmp_path / "p"
    manager.scaffold(prefix)
    assert manager.scaffold(prefix) == []  # 二次调用零动作


def test_scaffold_never_touches_existing_real_pfx(tmp_path):
    prefix = tmp_path / "p"
    prefix.mkdir()
    (prefix / "pfx").mkdir()  # Steam/直调风格真实目录
    (prefix / "pfx" / "marker").write_text("keep", encoding="utf-8")
    manager.scaffold(prefix)
    assert not (prefix / "pfx").is_symlink()
    assert (prefix / "pfx" / "marker").read_text() == "keep"


def test_detect_layouts(tmp_path):
    a = tmp_path / "a"; a.mkdir(); (a / "pfx").mkdir()
    assert detect(a) is PrefixLayout.REAL_DIR
    b = tmp_path / "b"; b.mkdir(); (b / "pfx").symlink_to(b, target_is_directory=True)
    assert detect(b) is PrefixLayout.SELF_SYMLINK
    assert detect(tmp_path / "nope") is PrefixLayout.MISSING


def test_check_version_states(tmp_path):
    proton = make_proton(tmp_path / "protos")
    fresh = tmp_path / "fresh"
    assert manager.check_version(fresh, proton) == "no_prefix"
    matched = tmp_path / "matched"
    matched.mkdir()
    (matched / "version").write_text("11.0-100", encoding="utf-8")
    assert manager.check_version(matched, proton) == "match"
    old = tmp_path / "old"
    old.mkdir()
    (old / "version").write_text("9.0-4", encoding="utf-8")
    assert manager.check_version(old, proton) == "upgrade_needed"
    # 脚本里没有常量 → unknown
    d = tmp_path / "protos2" / "Weird"
    d.mkdir(parents=True)
    (d / "proton").write_text("#!/bin/sh\n", encoding="utf-8")
    weird = ProtonVersion(name="Weird", path=d, proton_script=d / "proton",
                          version_str="", source="steam")
    assert manager.check_version(matched, weird) == "unknown"


def test_expected_prefix_version_extracts_constant(tmp_path):
    proton = make_proton(tmp_path / "p9", 'CURRENT_PREFIX_VERSION="GE-Proton11-3"')
    assert manager.expected_prefix_version(proton) == "GE-Proton11-3"


def test_is_managed(tmp_path):
    steamlike = tmp_path / "compatdata" / "123"
    steamlike.mkdir(parents=True)
    assert manager.is_managed(steamlike) is True
    plain = tmp_path / "box"
    plain.mkdir()
    assert manager.is_managed(plain) is False
    with_cfg = tmp_path / "cfg"
    with_cfg.mkdir()
    (with_cfg / "config_info").write_text("x", encoding="utf-8")
    assert manager.is_managed(with_cfg) is True
