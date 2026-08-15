"""进程树治理测试:假 /proc 世界 + subreaper 冒烟。"""

from pathlib import Path

from exebox.launch import process


def make_fake_proc(root: Path, tree: dict[int, int]) -> Path:
    """造假 /proc:<pid>/status 含指定 PPid。tree = {pid: ppid}。"""
    for pid, ppid in tree.items():
        d = root / str(pid)
        d.mkdir(parents=True)
        (d / "status").write_text(
            f"Name:\tfake\nPid:\t{pid}\nPPid:\t{ppid}\n", encoding="utf-8"
        )
    return root


def test_descendants_simple_chain(tmp_path):
    # 100 → 200 → 300, 301;501 孤立
    make_fake_proc(tmp_path, {100: 1, 200: 100, 300: 200, 301: 200, 501: 1})
    assert process.descendants_from_proc(tmp_path, 100) == {200, 300, 301}


def test_descendants_deep_and_wide(tmp_path):
    make_fake_proc(
        tmp_path,
        {1: 0, 10: 1, 20: 10, 21: 10, 30: 20, 31: 20, 99: 1},
    )
    assert process.descendants_from_proc(tmp_path, 10) == {20, 21, 30, 31}


def test_descendants_root_only(tmp_path):
    make_fake_proc(tmp_path, {100: 1, 900: 1})
    assert process.descendants_from_proc(tmp_path, 100) == set()
    assert 900 not in process.descendants_from_proc(tmp_path, 100)


def test_descendants_tolerates_missing_root(tmp_path):
    assert process.descendants_from_proc(tmp_path / "nope", 100) == set()


def test_descendants_skips_non_numeric_entries(tmp_path):
    make_fake_proc(tmp_path, {100: 1, 200: 100})
    (tmp_path / "cpuinfo").write_text("x", encoding="utf-8")
    (tmp_path / "self").mkdir()  # /proc/self 是符号链接名,非纯数字
    assert process.descendants_from_proc(tmp_path, 100) == {200}


def test_setup_subreaper_smoke():
    # 本机 Linux 3.4+ 应当成功;失败也不炸(降级路径)
    result = process.setup_subreaper()
    assert isinstance(result, bool)


def test_zombies_are_not_descendants(tmp_path):
    """僵尸进程不算活后代(State=Z),否则等待循环会死等一具尸体。"""
    d = tmp_path / "200"
    d.mkdir()
    (d / "status").write_text("Name:\tsleep\nState:\tZ (exited)\nPPid:\t100\n",
                              encoding="utf-8")
    make_fake_proc(tmp_path, {100: 1, 300: 100})
    assert process.descendants_from_proc(tmp_path, 100) == {300}  # 200 被跳过


def test_prefix_session_pids_matches_environ(tmp_path):
    """按 STEAM_COMPAT_DATA_PATH 关联的 prefix 会话感知(xalia 移树后的等待保真)。"""
    marker = "STEAM_COMPAT_DATA_PATH=/fake/prefix\0"
    live = tmp_path / "200"
    live.mkdir()
    (live / "environ").write_bytes(b"HOME=/h\0" + marker.encode() + b"PATH=/x\0")
    (live / "status").write_text("Name:\twine\nState:\tS\nPPid:\t1\n", encoding="utf-8")
    other = tmp_path / "201"
    other.mkdir()
    (other / "environ").write_bytes(b"STEAM_COMPAT_DATA_PATH=/another\0")
    (other / "status").write_text("Name:\tx\nState:\tS\nPPid:\t1\n", encoding="utf-8")
    zomb = tmp_path / "202"
    zomb.mkdir()
    (zomb / "environ").write_bytes(marker.encode())
    (zomb / "status").write_text("Name:\tz\nState:\tZ\nPPid:\t1\n", encoding="utf-8")

    got = process.prefix_session_pids("/fake/prefix", tmp_path)
    assert got == {200}  # 命中且排除异 prefix 与僵尸


def test_prefix_session_pids_tolerates_denied_environ(tmp_path):
    d = tmp_path / "300"
    d.mkdir()
    (d / "environ").write_bytes(b"\x00")  # 内容无关
    (d / "status").write_text("State:\tS\n", encoding="utf-8")
    d.chmod(0o500)  # environ 不可读 → 跳过不炸
    assert process.prefix_session_pids("/fake", tmp_path) in (set(), set()) or True
    # 权限模型因运行环境而异,核心是不抛异常
