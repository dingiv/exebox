from pathlib import Path

import pytest

from exebox.errors import NoProtonFoundError, ProtonNotFoundError
from exebox.proton.resolver import ProtonResolver


def make_proton(base: Path, name: str, version: str = "1.0-1") -> Path:
    d = base / name
    (d / "files").mkdir(parents=True, exist_ok=True)
    (d / "proton").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    (d / "version").write_text(version, encoding="utf-8")
    return d


@pytest.fixture()
def fake_steam(tmp_path) -> Path:
    home = tmp_path / "Steam"
    make_proton(home / "steamapps/common", "Proton - Experimental", "exp-11.0-x")
    make_proton(home / "steamapps/common", "Proton 9.0", "9.0-4")
    make_proton(home / "compatibilitytools.d", "GE-Proton11-3", "ge-11-3")
    # 干扰项:没有 proton 脚本的目录不算
    (home / "steamapps/common/SteamLinuxRuntime_sniper").mkdir(parents=True)
    return home


def test_list_available_order_compat_first(fake_steam):
    r = ProtonResolver(fake_steam)
    versions = r.list_available()
    names = [v.name for v in versions]
    assert names == ["GE-Proton11-3", "Proton - Experimental", "Proton 9.0"]
    assert versions[0].source == "compatibilitytools"
    assert versions[1].source == "steam"
    assert versions[1].version_str == "exp-11.0-x"
    assert versions[0].proton_script == versions[0].path / "proton"


def test_resolve_exact(fake_steam):
    r = ProtonResolver(fake_steam)
    assert r.resolve("GE-Proton11-3").name == "GE-Proton11-3"
    assert r.resolve("Proton 9.0").version_str == "9.0-4"


def test_resolve_default_is_experimental(fake_steam):
    assert ProtonResolver(fake_steam).resolve(None).name == "Proton - Experimental"


def test_resolve_fuzzy_match(fake_steam):
    r = ProtonResolver(fake_steam)
    assert r.resolve("proton-experimental").name == "Proton - Experimental"
    assert r.resolve("ProtonExperimental").name == "Proton - Experimental"
    assert r.resolve("ge proton 11 3").name == "GE-Proton11-3"


def test_resolve_missing_lists_available(fake_steam):
    with pytest.raises(ProtonNotFoundError, match="本机可用.*Proton - Experimental"):
        ProtonResolver(fake_steam).resolve("Proton 99.0")


def test_no_proton_at_all(tmp_path):
    with pytest.raises(NoProtonFoundError, match="未发现任何 Proton"):
        ProtonResolver(tmp_path).list_available()
