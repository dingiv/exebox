"""prefix reset 生命周期测试(三道闸 + 重建)。"""


import pytest

from exebox.errors import PrefixError
from exebox.prefix.lifecycle import reset


def test_reset_rebuilds_scaffold(tmp_path):
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (prefix / "junk.txt").write_text("脏数据", encoding="utf-8")
    reset(prefix, tmp_path)
    assert not (prefix / "junk.txt").exists()  # 脏的没了
    assert (prefix / "tracked_files").is_file()  # 脚手架重建
    assert (prefix / "pfx").is_symlink()


def test_reset_refuses_managed(tmp_path):
    compatdata = tmp_path / "steamapps" / "compatdata" / "123"
    compatdata.mkdir(parents=True)
    with pytest.raises(PrefixError, match="Steam 托管"):
        reset(compatdata, tmp_path)


def test_reset_refuses_running_box(tmp_path):
    import os

    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (tmp_path / "run.pid").write_text(str(os.getpid()), encoding="utf-8")  # 自己 = "活着"
    with pytest.raises(PrefixError, match="正在运行"):
        reset(prefix, tmp_path)


def test_reset_stale_pid_allows(tmp_path):
    prefix = tmp_path / "prefix"
    prefix.mkdir()
    (tmp_path / "run.pid").write_text("999999", encoding="utf-8")  # 死 pid 不拦
    reset(prefix, tmp_path)
    assert (prefix / "tracked_files").is_file()
