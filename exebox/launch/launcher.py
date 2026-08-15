"""Launcher:启动编排(design §6)。

plan/dry_run 为纯计算(解析引擎、组装环境/命令、算日志路径,零副作用);
launch 才做 scaffold + Popen + 生命周期管理。
"""

import os
import signal
import subprocess
import time
from collections.abc import Callable

from exebox.config import Config
from exebox.errors import LaunchError, PrefixVersionError, ProtonError
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

    @property
    def config(self) -> Config:
        return self._config

    def plan(
        self,
        manifest: GameManifest,
        extra_env: dict[str, str] | None = None,
        require_cwd: bool = True,
    ) -> LaunchPlan:
        """纯计算:将要执行的命令、环境、cwd、日志路径。

        require_cwd=False 供安装流程使用(游戏目录还没建,装完才存在)。
        """
        try:
            proton = self._resolver.resolve(manifest.proton)
        except ProtonError as e:
            raise LaunchError(str(e)) from e
        if require_cwd and not manifest.game_dir.is_dir():
            raise LaunchError(
                f"game_dir 不存在: {manifest.game_dir}"
                f"(cwd 契约:启动前必须就位,见 design §6.2;安装流程不受此限)"
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
        self,
        manifest: GameManifest,
        extra_env: dict[str, str] | None = None,
        confirm: Callable[[str], bool] | None = None,
    ) -> LaunchResult:
        """启动。confirm 是"升级不可逆,继续?"的问答回调(CLI 传 typer.confirm,
        GUI 可注入自己的对话框);None 时需要确认的场景一律拒绝(安全默认)。
        """
        plan = self.plan(manifest, extra_env)
        self.notes = []

        # 前置:托管 prefix 不动结构;版本棘轮拦截(M3)
        if not manager.is_managed(manifest.prefix):
            for a in manager.scaffold(manifest.prefix):
                self.notes.append(f"scaffold: {a}")
        verdict = manager.check_version(manifest.prefix, plan.proton)
        if verdict == "upgrade_needed":
            if manager.is_managed(manifest.prefix):
                raise PrefixVersionError(
                    f"{manifest.slug}: prefix 由 Steam 托管且版本与 "
                    f"{plan.proton.name} 不一致,拒绝启动(让 Steam 自己升级它)"
                )
            question = (
                f"{manifest.slug}: prefix 版本与 {plan.proton.name} 不一致,"
                f"启动将触发不可逆升级。继续?"
            )
            if confirm is None or not confirm(question):
                raise PrefixVersionError(question + " —— 未获确认,拒绝启动")
            self.notes.append("棘轮升级已获确认")
        elif verdict == "unknown":
            self.notes.append("⚠ 无法确定目标 Proton 的 prefix 版本,跳过棘轮检查")

        if not process.setup_subreaper():
            self.notes.append("⚠ subreaper 设置失败,降级为简单等待(孤儿进程可能残留)")

        log_file = open_launch_log(plan.log_path)
        t0 = time.monotonic()
        old_int = signal.getsignal(signal.SIGINT)
        old_term = signal.getsignal(signal.SIGTERM)
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
            # 引导器模式(M3 实测 MO3):被跟踪的 exe 是引导壳,拉起真身后自己退出,
            # proton run 只等被请求的 exe 就返回 —— 但真身子代已被 subreaper 过继
            # 给我们,继续等它们跑完(期间 Ctrl-C 照常收割全树)。
            # v1.1 修正:wine 陪跑服务可能无视 SIGTERM,等待必须有出口 ——
            # 已被信号收割或超过耐心上限时,SIGKILL 清场并退出,绝不无限等。
            grace = 0.0
            while process.descendants(os.getpid()):
                if process.last_signal is not None or grace >= 30.0:
                    process.kill_descendants_of_self(signal.SIGKILL)
                    time.sleep(0.5)
                    stubborn = process.descendants(os.getpid())
                    if stubborn:
                        self.notes.append(
                            f"⚠ {len(stubborn)} 个进程拒绝退出(D 状态?),已放弃等待"
                        )
                    break
                time.sleep(0.5)
                grace += 0.5
            # 兜底清扫(空集即无操作)
            process.kill_descendants_of_self(signal.SIGTERM)
            if process.last_signal is not None:
                exit_code = -process.last_signal  # 如实报告"被信号 N 杀死"
        finally:
            # 恢复调用方原有的信号处理(launch 不该永久劫持宿主进程;
            # 否则 pytest/timeout 的 SIGTERM 会被吞,进程杀不死 —— 实测教训)
            signal.signal(signal.SIGINT, old_int)
            signal.signal(signal.SIGTERM, old_term)
            log_file.close()
        return LaunchResult(
            exit_code=exit_code,
            pid=proc.pid,
            duration_seconds=time.monotonic() - t0,
            log_path=plan.log_path,
        )
