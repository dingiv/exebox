"""install steps 执行器测试:fake proton 记录命令行,真实文件系统测 copy/mkdir。"""

from pathlib import Path

import pytest

from exebox.errors import StepExecutionError
from exebox.install.steps import run_step
from exebox.models import InstallStep

ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp"}


def make_fake_proton(tmp_path: Path, body: str = "exit 0") -> Path:
    script = tmp_path / "proton"
    script.write_text(f"#!/bin/bash\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    return script


@pytest.fixture()
def recorder(tmp_path) -> Path:
    """fake proton:把收到的参数追加到 record 文件。"""
    rec = tmp_path / "record.txt"
    return make_fake_proton(
        tmp_path, f'printf "%s\\n" "$@" >> "{rec}"'
    ) and rec


def test_shell_step_records_relative_form(tmp_path, recorder):
    proton = make_fake_proton(
        tmp_path, f'printf "%s\\n" "$@" >> "{tmp_path / "rec.txt"}"'
    )
    cwd = tmp_path / "game"
    cwd.mkdir()
    (cwd / "setup.exe").write_text("x", encoding="utf-8")
    step = InstallStep(
        description="静默安装", type="shell",
        command=["/abs/other.exe", "/S"] if False else [str(cwd / "setup.exe"), "/S"],
    )
    with open(tmp_path / "log", "w") as log:
        run_step(step, proton, ENV, cwd, log)
    lines = (tmp_path / "rec.txt").read_text().splitlines()
    assert lines == ["run", "./setup.exe", "/S"]  # cwd 内 → ./相对契约


def test_reg_add_builds_full_command(tmp_path):
    rec = tmp_path / "rec.txt"
    proton = make_fake_proton(tmp_path, f'printf "%s\\n" "$@" >> "{rec}"')
    step = InstallStep(
        description="Westwood InstallPath", type="reg_add",
        key=r"Software\Westwood\Red Alert 2",
        value_name="InstallPath",
        value=r"C:\Games\RA2\RA2.EXE",
        reg_arch="32",
    )
    with open(tmp_path / "log", "w") as log:
        run_step(step, proton, ENV, tmp_path, log)
    got = (tmp_path / "rec.txt").read_text().splitlines()
    assert got[:3] == ["run", "reg", "add"]
    assert got[3] == r"HKLM\Software\Westwood\Red Alert 2"
    for needle in ("/v", "InstallPath", "/t", "REG_SZ", "/d", "C:\\Games\\RA2\\RA2.EXE", "/f", "/reg:32"):
        assert needle in got


def test_reg_add_requires_triple(tmp_path):
    proton = make_fake_proton(tmp_path)
    step = InstallStep(description="缺 value_name", type="reg_add", key="K", value="V")
    with (
        open(tmp_path / "log", "w") as log,
        pytest.raises(StepExecutionError, match="value_name"),
    ):
        run_step(step, proton, ENV, tmp_path, log)


def test_copy_step_to_file_and_dir(tmp_path):
    proton = make_fake_proton(tmp_path)
    src = tmp_path / "a.bin"
    src.write_text("data", encoding="utf-8")
    dst_dir = tmp_path / "dst"
    dst_dir.mkdir()
    with open(tmp_path / "log", "w") as log:
        run_step(InstallStep(description="入目录", type="copy", src=src, dst=dst_dir),
                 proton, ENV, tmp_path, log)
        assert (dst_dir / "a.bin").read_text() == "data"
        dst_file = tmp_path / "sub" / "b.bin"
        run_step(InstallStep(description="到文件", type="copy", src=src, dst=dst_file),
                 proton, ENV, tmp_path, log)
    assert dst_file.read_text() == "data"


def test_mkdir_step_nested(tmp_path):
    proton = make_fake_proton(tmp_path)
    target = tmp_path / "x" / "y" / "z"
    with open(tmp_path / "log", "w") as log:
        run_step(InstallStep(description="建目录", type="mkdir", dst=target),
                 proton, ENV, tmp_path, log)
    assert target.is_dir()


def test_failing_proton_raises(tmp_path):
    proton = make_fake_proton(tmp_path, "exit 3")
    with (
        open(tmp_path / "log", "w") as log,
        pytest.raises(StepExecutionError, match="退出码 3"),
    ):
        run_step(
            InstallStep(description="会失败", type="shell", command=["whatever.exe"]),
            proton, ENV, tmp_path, log,
        )
