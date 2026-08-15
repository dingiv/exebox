"""exebox CLI —— 唯一允许 print 的层(typer + rich)。

v1(M1):仅 list。launch/install 在 M2/M3 加入。
"""

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from exebox.config import Config
from exebox.errors import ExeboxError
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
