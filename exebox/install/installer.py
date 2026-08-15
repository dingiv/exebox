"""Installer:安装编排(design §7)。

流程:scaffold prefix → 跑安装器(install.source)→ 顺序跑 steps → 校验 exe 就位。
安装器与 steps 共用启动同款环境(ProtonRunner.build_environment),
零隐藏参数原则同样适用于安装期。
"""

import signal
import subprocess
import time

from exebox.errors import InstallError, ProtonError
from exebox.install.steps import run_step
from exebox.launch import process
from exebox.launch.launcher import Launcher
from exebox.models import GameManifest, LaunchResult
from exebox.prefix import manager
from exebox.proton.runner import ProtonRunner


class Installer:
    def __init__(self, launcher: Launcher):
        self._launcher = launcher

    def install(
        self,
        manifest: GameManifest,
        run_installer: bool = True,
    ) -> LaunchResult | None:
        """执行安装。run_installer=False 跳过安装器(仅跑 steps,用于修复重放)。
        返回安装器进程的 LaunchResult(未跑安装器则 None)。
        """
        if manifest.install is None:
            raise InstallError(
                f"{manifest.slug}: 清单没有 install 段,无法安装(只是导入?)"
            )
        try:
            plan = self._launcher.plan(manifest, require_cwd=False)
        except ProtonError as e:
            raise InstallError(str(e)) from e

        if not manager.is_managed(manifest.prefix):
            manager.scaffold(manifest.prefix)
        manifest.game_dir.mkdir(parents=True, exist_ok=True)

        log_path = manifest.box_path / "logs" / "install.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        result: LaunchResult | None = None
        with open(log_path, "a", encoding="utf-8", errors="replace") as log:
            log.write(f"\n# install {manifest.slug} @ {time.strftime('%F %T')}\n")
            env = ProtonRunner(
                plan.proton, self._launcher.config.steam_install_path
            ).build_environment(manifest)

            if run_installer:
                result = self._run_installer(manifest, plan, env, log)

            for step in manifest.install.steps:
                log.write(f"\n# step: {step.description} ({step.type})\n")
                log.flush()
                run_step(step, plan.proton.proton_script, env, manifest.game_dir, log)

        if not manifest.exe.exists():
            raise InstallError(
                f"安装流程跑完但 exe 仍未就位: {manifest.exe}"
                f"(检查安装日志 {log_path};安装器可能需要交互或装到了别处)"
            )
        return result

    def _run_installer(self, manifest, plan, env, log) -> LaunchResult:
        source = manifest.install.source
        if not source.exists():
            raise InstallError(f"安装器不存在: {source}")
        # exe 参数形态契约同样适用于安装器:cwd 内用 ./相对
        try:
            rel = source.relative_to(manifest.game_dir)
            exe_arg = f"./{rel}"
        except ValueError:
            exe_arg = str(source)
        cmd = [str(plan.proton.proton_script), manifest.verb, exe_arg]
        log.write(f"\n$ {' '.join(cmd)}\n")
        log.flush()
        t0 = time.monotonic()
        proc = subprocess.Popen(
            cmd, env=env, cwd=manifest.game_dir,
            start_new_session=True, stdout=log, stderr=subprocess.STDOUT,
        )
        process.install_signal_handlers()
        exit_code = proc.wait()
        process.kill_descendants_of_self(signal.SIGTERM)
        if exit_code != 0:
            raise InstallError(
                f"安装器退出码 {exit_code}(详见安装日志;GUI 安装器被取消?)"
            )
        return LaunchResult(
            exit_code=exit_code, pid=proc.pid,
            duration_seconds=time.monotonic() - t0, log_path=None,
        )
