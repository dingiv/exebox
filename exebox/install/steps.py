"""install step 执行器(design §7.3)。

shell   —— 经同一 Proton/环境执行(安装期环境 = 启动期环境,无隐藏差异)
reg_add —— 经 proton 跑 reg add(32 位程序要记得 reg_arch: "32")
copy    —— 纯文件系统拷贝(src→dst;dst 为目录则拷入)
mkdir   —— mkdir -p 语义

任一步失败抛 StepExecutionError,整个安装中止。
调用方(installer)负责提供:env(已组装)、proton 脚本路径、日志文件。
"""

import shutil
import subprocess
from pathlib import Path

from exebox.errors import StepExecutionError
from exebox.models import InstallStep


def run_step(
    step: InstallStep,
    proton_script: Path,
    env: dict[str, str],
    cwd: Path,
    log_file,
) -> None:
    """执行一个 step;log_file 为已打开的日志(调用方管理开关)。"""
    handler = {
        "shell": _run_shell,
        "reg_add": _run_reg_add,
        "copy": _run_copy,
        "mkdir": _run_mkdir,
    }.get(step.type)
    if handler is None:
        raise StepExecutionError(f"[{step.description}] 不支持的 type: {step.type}")
    handler(step, proton_script, env, cwd, log_file)


def _run_shell(step, proton_script: Path, env, cwd: Path, log_file) -> None:
    if not step.command:
        raise StepExecutionError(f"[{step.description}] shell 步骤缺 command")
    exe = step.command[0]
    args = step.command[1:]
    try:
        rel = Path(exe).relative_to(cwd)
        exe_arg = f"./{rel}"
    except ValueError:
        exe_arg = exe  # 与 launch 同款契约:cwd 内用 ./相对,否则绝对
    _exec(
        [str(proton_script), "run", exe_arg, *args],
        env, cwd, log_file, step.description,
    )


def _run_reg_add(step, proton_script: Path, env, cwd: Path, log_file) -> None:
    if not step.key or step.value is None or not step.value_name:
        raise StepExecutionError(
            f"[{step.description}] reg_add 需要 key / value_name / value 三件套"
        )
    hive = step.reg_hive or "HKLM"
    vtype = "REG_DWORD" if (step.value_type or "").upper() == "DWORD" else "REG_SZ"
    cmd = [
        str(proton_script), "run", "reg", "add",
        f"{hive}\\{step.key}",
        "/v", step.value_name,
        "/t", vtype,
        "/d", step.value,
        "/f",
    ]
    if step.reg_arch in ("32", "64"):
        cmd.append(f"/reg:{step.reg_arch}")
    _exec(cmd, env, cwd, log_file, step.description)


def _run_copy(step, proton_script: Path, env, cwd: Path, log_file) -> None:
    if not step.src or not step.dst:
        raise StepExecutionError(f"[{step.description}] copy 步骤缺 src/dst")
    try:
        if step.dst.is_dir():
            shutil.copy2(step.src, step.dst / step.src.name)
        else:
            step.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(step.src, step.dst)
    except OSError as e:
        raise StepExecutionError(f"[{step.description}] copy 失败: {e}") from e


def _run_mkdir(step, proton_script: Path, env, cwd: Path, log_file) -> None:
    if not step.dst:
        raise StepExecutionError(f"[{step.description}] mkdir 步骤缺 dst")
    try:
        step.dst.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise StepExecutionError(f"[{step.description}] mkdir 失败: {e}") from e


def _exec(cmd: list[str], env, cwd: Path, log_file, desc: str) -> None:
    log_file.write(f"\n$ {' '.join(cmd)}\n")
    log_file.flush()
    proc = subprocess.run(
        cmd, env=env, cwd=cwd, start_new_session=True, check=False,
        stdout=log_file, stderr=subprocess.STDOUT,
    )
    if proc.returncode != 0:
        raise StepExecutionError(f"[{desc}] 退出码 {proc.returncode}(详见安装日志)")
