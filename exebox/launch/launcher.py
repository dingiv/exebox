"""Launcher:启动编排(design §6)。

plan/dry_run 为纯计算(解析引擎、组装环境/命令、算日志路径,零副作用);
launch 才做 scaffold + Popen + 生命周期管理。
"""

import signal
import subprocess
import time

from exebox.config import Config
from exebox.errors import LaunchError, ProtonError
from exebox.launch import process
from exebox.launch.logger import new_log_path, open_launch_log
from exebox.models import GameManifest, LaunchResult
from exebox.prefix import manager
from exebox.proton.resolver import ProtonResolver
from exebox.proton.runner import LaunchPlan, ProtonRunner


class Launcher:
    def __init__(self, config: Config | None = None, resolver: ProtonResolver | None = None):
        self._config = config or Config.from_env()
        self._resolver = resolver or ProtonResolver()
        self.notes: list[str] = []  # 最近一次 launch 的过程通知(scaffold/降级/警告)

    def plan(
        self, manifest: GameManifest, extra_env: dict[str, str] | None = None
    ) -> LaunchPlan:
        """纯计算:将要执行的命令、环境、cwd、日志路径。"""
        try:
            proton = self._resolver.resolve(manifest.proton)
        except ProtonError as e:
            raise LaunchError(str(e)) from e
        if not manifest.game_dir.is_dir():
            raise LaunchError(
                f"game_dir 不存在: {manifest.game_dir}"
                f"(cwd 契约:启动前必须就位,见 design §6.2)"
            )
        runner = ProtonRunner(proton, self._config.steam_install_path)
        return LaunchPlan(
            command=runner.build_command(manifest),
            env=runner.build_environment(manifest, extra_env=extra_env),
            cwd=manifest.game_dir,
            log_path=new_log_path(manifest.box_path),
            proton=proton,
        )

    def dry_run(
        self, manifest: GameManifest, extra_env: dict[str, str] | None = None
    ) -> LaunchPlan:
        """plan 的别名,语义显式:不产生任何副作用。"""
        return self.plan(manifest, extra_env)

    def launch(
        self, manifest: GameManifest, extra_env: dict[str, str] | None = None
    ) -> LaunchResult:
        plan = self.plan(manifest, extra_env)
        self.notes = []

        # 前置:托管 prefix 不动结构;版本不一致先警告(M3 起才拦截)
        if not manager.is_managed(manifest.prefix):
            for a in manager.scaffold(manifest.prefix):
                self.notes.append(f"scaffold: {a}")
        verdict = manager.check_version(manifest.prefix, plan.proton)
        if verdict == "upgrade_needed":
            self.notes.append(
                "⚠ prefix 版本与目标 Proton 不一致,启动将触发不可逆升级"
                "(M3 起此处将要求显式确认)"
            )
        elif verdict == "unknown":
            self.notes.append("⚠ 无法确定目标 Proton 的 prefix 版本,跳过棘轮检查")

        if not process.setup_subreaper():
            self.notes.append("⚠ subreaper 设置失败,降级为简单等待(孤儿进程可能残留)")

        log_file = open_launch_log(plan.log_path)
        t0 = time.monotonic()
        try:
            proc = subprocess.Popen(
                plan.command,
                env=plan.env,
                cwd=plan.cwd,
                start_new_session=True,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
            process.install_signal_handlers()
            exit_code = proc.wait()
            # 兜底清扫:xalia double-fork 出的进程已被 subreaper 过继给我们,
            # 正常退出后也可能有残留(Svchost 类陪跑),SIGTERM 一遍,空集即无操作
            process.kill_descendants_of_self(signal.SIGTERM)
        finally:
            log_file.close()
        return LaunchResult(
            exit_code=exit_code,
            pid=proc.pid,
            duration_seconds=time.monotonic() - t0,
            log_path=plan.log_path,
        )
