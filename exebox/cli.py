"""exebox CLI —— 唯一允许 print 的层(typer + rich)。

v1(M1)list;M2 加入 launch;M3 加入 install。
"""

import os
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from exebox.config import Config
from exebox.errors import ExeboxError
from exebox.launch.launcher import Launcher
from exebox.proton.resolver import ProtonResolver
from exebox.registry.store import RegistryStore

app = typer.Typer(
    help="wine/proton 的前端:声明式清单管理 Windows 程序。",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)


@app.callback()
def callback() -> None:
    """exebox —— 安装 exe、管理 exe、启动 exe。"""


@app.command("list")
def list_games(
    show_all: bool = typer.Option(False, "--all", help="附健康检查列"),
    protons: bool = typer.Option(False, "--protons", help="列出本机可用 Proton"),
) -> None:
    """列出库中全部游戏(或本机 Proton)。"""
    if protons:
        _list_protons()
        return
    _list_games(show_all)


def _list_protons() -> None:
    resolver = ProtonResolver()
    table = Table(title=None, box=None, pad_edge=False)
    table.add_column("PROTON", style="cyan")
    table.add_column("VERSION", style="dim")
    table.add_column("SOURCE", style="dim")
    table.add_column("PATH", style="dim", overflow="fold")
    for pv in resolver.list_available():
        table.add_row(pv.name, pv.version_str, pv.source, _short(pv.path))
    console.print(table)


def _list_games(show_all: bool) -> None:
    config = Config.from_env()
    store = RegistryStore(config.library_root)
    games = store.games()

    if not games:
        console.print(
            f"[dim]库是空的:{_short(config.library_root)} 下没有找到任何 game.yaml"
            f"(先运行 exebox install,或手写清单后放进来)[/dim]"
        )
        for path, err in store.failures():
            err_console.print(f"[red]✗[/red] {_short(path)}: {err}")
        return

    table = Table(title=None, box=None, pad_edge=False)
    table.add_column("NAME", style="bold")
    table.add_column("SLUG", style="cyan")
    table.add_column("PROTON", style="magenta")
    table.add_column("PREFIX", overflow="fold")
    if show_all:
        table.add_column("EXE")
        table.add_column("CWD")
        table.add_column("VERSION")

    resolver = ProtonResolver()
    for m in games.values():
        row = [m.name, m.slug, m.proton, _short(m.prefix)]
        if show_all:
            row += [
                _ok(m.exe.exists()),
                _ok(m.game_dir.is_dir()),
                _prefix_version(m.prefix),
            ]
        table.add_row(*row)
    console.print(table)
    console.print(f"[dim]{len(games)} 个程序注册于 {_short(config.library_root)}[/dim]")

    for path, err in store.failures():
        err_console.print(f"[red]✗ 坏清单[/red] {_short(path)}: {err}")

    if show_all:
        # 顺带校验引擎名可解析
        for m in games.values():
            try:
                resolver.resolve(m.proton)
            except ExeboxError as e:
                err_console.print(f"[red]✗[/red] {m.slug}: {e}")


@app.command("launch")
def launch_cmd(
    slug: str = typer.Argument(..., help="箱目录名(exebox list 可查)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="打印将执行的命令与环境,不启动"),
    full: bool = typer.Option(
        False, "--full", help="dry-run 时显示全量继承环境(默认只显示 exebox 改动的键)"
    ),
    env: list[str] = typer.Option(
        None, "--env", help="临时环境变量 K=V,可重复,优先级高于清单"
    ),
) -> None:
    """按清单启动一个程序。"""
    manifest = _find_manifest(slug)
    extra_env = _parse_env_options(env)
    launcher = Launcher(Config.from_env())

    if dry_run:
        plan = launcher.dry_run(manifest, extra_env)
        _print_dry_run(manifest, plan, full)
        return

    plan = launcher.plan(manifest, extra_env)
    _print_launch_header(manifest, plan)
    result = launcher.launch(manifest, extra_env)
    for note in launcher.notes:
        console.print(f"[yellow]{note}[/yellow]")
    mins, secs = divmod(int(result.duration_seconds), 60)
    if result.exit_code == 0:
        console.print(
            f"[green]exited 0[/green] ({mins}m{secs:02d}s)  log: {_short(result.log_path)}"
        )
    elif result.exit_code < 0:
        console.print(
            f"[red]被信号 {-result.exit_code} 杀死[/red] ({mins}m{secs:02d}s)"
            f"  log: {_short(result.log_path)}"
        )
        raise typer.Exit(1)
    else:
        console.print(
            f"[red]exited {result.exit_code}[/red] ({mins}m{secs:02d}s)"
            f"  log: {_short(result.log_path)}"
        )
        raise typer.Exit(result.exit_code)


_SECRET_KEY_RE = re.compile(r"(?i)(token|secret|password|passwd|api_key|auth)")


def _redact(key: str, value: str) -> str:
    if _SECRET_KEY_RE.search(key) and len(value) > 4:
        return value[:4] + "***"
    return value


def _print_dry_run(manifest, plan, full: bool) -> None:
    lines = ["[bold]Command[/bold]"]
    lines += [f"  [cyan]{c}[/cyan]" for c in plan.command]
    lines.append("")

    if full:
        shown = plan.env
        title = f"Environment(全量 {len(plan.env)} 项,机密已打码)"
    else:
        shown = {k: v for k, v in plan.env.items() if os.environ.get(k) != v}
        inherited = len(plan.env) - len(shown)
        title = f"Environment(exebox 改动 {len(shown)} 项;其余 {inherited} 项原样继承,--full 查看)"
    lines.append(f"[bold]{title}[/bold]")
    lines += [f"  {k}={_redact(k, v)}" for k, v in sorted(shown.items())]
    lines.append("")
    lines.append(f"[bold]cwd[/bold] = {plan.cwd}")
    console.print(Panel("\n".join(lines), title=f"dry-run: {manifest.slug}", expand=False))


def _find_manifest(slug: str):
    store = RegistryStore(Config.from_env().library_root)
    games = store.games()
    if slug not in games:
        available = ", ".join(sorted(games)) or "(库是空的)"
        err_console.print(f"[red]✗[/red] 找不到 '{slug}'。可用: {available}")
        raise typer.Exit(1)
    return games[slug]


def _parse_env_options(env: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in env or []:
        if "=" not in item:
            err_console.print(f"[red]✗[/red] --env 需要 K=V 形式,得到: {item}")
            raise typer.Exit(1)
        k, v = item.split("=", 1)
        out[k] = v
    return out


def _print_launch_header(manifest, plan) -> None:
    console.print(f"[bold]Launching {manifest.name}[/bold]")
    console.print(f"  Proton  {plan.proton.name} ({plan.proton.version_str})")
    console.print(f"  Exe     {manifest.exe}")
    console.print(f"  Cwd     {plan.cwd}")
    console.print(f"  Prefix  {manifest.prefix}")
    merged = dict(manifest.env)
    if manifest.dll_overrides and "WINEDLLOVERRIDES" not in merged:
        merged["WINEDLLOVERRIDES"] = manifest.dll_overrides
    if merged:
        shown = "  ".join(f"{k}={v}" for k, v in sorted(merged.items()))
        console.print(f"  Env+    {shown}")
    if manifest.path_append:
        console.print(f"  PATH+   {':'.join(str(p) for p in manifest.path_append)}")
    console.print(f"  Log     {plan.log_path}")


def _prefix_version(prefix: Path) -> str:
    vfile = Path(prefix) / "version"
    if vfile.is_file():
        return vfile.read_text(encoding="utf-8", errors="replace").strip() or "?"
    return "-"


def _ok(cond: bool) -> str:
    return "[green]✓[/green]" if cond else "[red]✗[/red]"


def _short(p: Path) -> str:
    s = str(p)
    home = str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


def main() -> None:
    app()


if __name__ == "__main__":
    main()
