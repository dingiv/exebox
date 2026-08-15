"""exebox CLI —— 唯一允许 print 的层(typer + rich)。

v1(M1)list;M2 加入 launch;M3 加入 install。
"""

import os
import re
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from exebox.config import Config
from exebox.errors import ExeboxError
from exebox.launch.launcher import Launcher
from exebox.manifest.loader import load
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


@app.command("install")
def install_cmd(
    source: str | None = typer.Argument(None, help="安装器 exe 路径(交互模式入口)"),
    manifest_file: Path | None = typer.Option(
        None, "--manifest", help="非交互:读现成清单注册(可配合 --run-installer)"
    ),
    slug: str | None = typer.Option(None, "--slug", help="覆盖箱目录名(默认取自清单)"),
    run_installer: bool = typer.Option(
        False, "--run-installer", help="写入清单后立即执行安装流程"
    ),
    skip_installer: bool = typer.Option(
        False, "--skip-installer", help="仅注册,不跑安装器(与 --run-installer 互斥)"
    ),
    import_mode: bool = typer.Option(
        False, "--import", help="交互向导但跳过安装器(存量程序导入)"
    ),
) -> None:
    """安装一个程序:向导生成清单 → (可选)跑安装器与步骤。"""
    if run_installer and skip_installer:
        err_console.print("[red]✗[/red] --run-installer 与 --skip-installer 互斥")
        raise typer.Exit(1)

    config = Config.from_env()
    launcher = Launcher(config)

    if manifest_file is not None:
        _install_from_manifest(config, launcher, manifest_file, slug, run_installer)
        return

    data = _wizard(source, import_mode, config)
    box = config.library_root / data["slug"]
    if (
        box.exists()
        and (box / "game.yaml").is_file()
        and not typer.confirm(f"箱 {data['slug']} 已有清单,覆盖?")
    ):
        raise typer.Exit(1)
    box.mkdir(parents=True, exist_ok=True)
    manifest_path = box / "game.yaml"
    manifest_path.write_text(
        yaml.safe_dump(data["manifest"], allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    console.print(f"[green]✓[/green] 清单已写入 {manifest_path}")
    RegistryStore(config.library_root).sync()

    if not import_mode and typer.confirm("现在运行安装器?", default=True):
        _do_install(launcher, manifest_path)


def _do_install(launcher: Launcher, manifest_path: Path) -> None:
    from exebox.install.installer import Installer

    manifest = load(manifest_path)
    console.print("[bold]安装中…[/bold](GUI 安装器请在弹出的窗口里操作)")
    try:
        Installer(launcher).install(manifest)
    except ExeboxError as e:
        err_console.print(f"[red]✗ 安装失败:[/red] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]✓ 安装完成[/green],试运行: exebox launch {manifest.slug}")


def _install_from_manifest(
    config: Config, launcher: Launcher, manifest_file: Path, slug: str | None,
    run_installer: bool,
) -> None:
    src = Path(manifest_file).expanduser()
    try:
        load(src)  # 只做校验
    except ExeboxError as e:
        err_console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1) from e
    name = slug or (src.parent.name if (src.parent / "game.yaml") == src else src.stem)
    box = config.library_root / name
    box.mkdir(parents=True, exist_ok=True)
    (box / "game.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    console.print(f"[green]✓[/green] 已注册 {name} → {box / 'game.yaml'}")
    RegistryStore(config.library_root).sync()
    if run_installer:
        _do_install(launcher, box / "game.yaml")


def _wizard(source: str | None, import_mode: bool, config: Config) -> dict:
    """8 步向导,产出 {slug, manifest(dict)}。每步默认值回车即取。"""
    resolver = ProtonResolver()
    protons = resolver.list_available()

    src = Path(source or typer.prompt("安装器 exe 路径")).expanduser()
    while not src.is_file():
        src = Path(typer.prompt("文件不存在,重新输入安装器路径")).expanduser()

    name = typer.prompt("程序名", default=src.stem)
    slug = typer.prompt(
        "箱目录名(slug,即启动 ID)", default=_slugify(name)
    )
    box = config.library_root / slug

    console.print("可用 Proton:")
    for i, pv in enumerate(protons, 1):
        console.print(f"  [{i}] {pv.name}  [dim]{pv.version_str}[/dim]")
    pi = typer.prompt("选择 Proton", default="1", type=int)
    proton_name = protons[max(0, min(pi, len(protons)) - 1)].name

    game_dir = Path(typer.prompt(
        "游戏目录(启动 cwd;默认装进箱内)", default=str(box / "game")
    )).expanduser()
    exe_name = typer.prompt("主 exe 文件名(相对游戏目录)", default=f"{src.stem}.exe")

    dll = typer.prompt("DLL 覆盖(如 ddraw=n,b,回车跳过)", default="")
    extra_args = typer.prompt("附加参数(空格分隔,回车跳过)", default="").split()

    manifest: dict = {
        "name": name,
        "exe": f"./{exe_name}",
        "proton": proton_name,
        "game_dir": str(game_dir),
    }
    prefix = typer.prompt(
        "prefix 目录(回车=箱内新建;或 existing:<路径> 复用)", default=str(box / "prefix")
    )
    if prefix.startswith("existing:"):
        manifest["prefix"] = prefix[len("existing:"):].strip()
    else:
        manifest["prefix"] = prefix
    if dll:
        manifest["dll_overrides"] = dll
    if extra_args:
        manifest["args"] = extra_args
    manifest["install"] = {"source": str(src)}

    console.print(Panel(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
                        title="生成的 game.yaml", expand=False))
    if not typer.confirm("写入这份清单?"):
        raise typer.Exit(1)
    return {"slug": slug, "manifest": manifest}


def _slugify(name: str) -> str:
    import re as _re

    s = _re.sub(r"[^0-9a-zA-Z一-鿿]+", "-", name).strip("-").lower()
    return s or "game"


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
        # 顺带校验引擎名可解析 + 路径告警
        for m in games.values():
            try:
                resolver.resolve(m.proton)
            except ExeboxError as e:
                err_console.print(f"[red]✗[/red] {m.slug}: {e}")
            for w in m.warnings:
                console.print(f"[yellow]⚠ {m.slug}:[/yellow] {w}")


@app.command("launch")
def launch_cmd(
    slug: str = typer.Argument(..., help="箱目录名(exebox list 可查)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="打印将执行的命令与环境,不启动"),
    full: bool = typer.Option(
        False, "--full", help="dry-run 时显示全量继承环境(默认只显示 exebox 改动的键)"
    ),
    bg: bool = typer.Option(
        False, "--bg", help="后台启动:打印 PID 后立即返回(可用 exebox ps 查看)"
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

    if bg:
        _launch_bg(slug, manifest, env or [])
        return

    plan = launcher.plan(manifest, extra_env)
    _print_launch_header(manifest, plan)
    try:
        result = launcher.launch(manifest, extra_env, confirm=typer.confirm)
    except ExeboxError as e:
        err_console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1) from e
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


def _launch_bg(slug: str, manifest, env_opts: list[str]) -> None:
    """后台启动:分离会话重新拉起自身(不带 --bg),落 run.pid。"""
    import subprocess
    import sys

    args = [sys.executable, "-m", "exebox", "launch", slug]
    for kv in env_opts:
        args += ["--env", kv]
    bg_log = manifest.box_path / "logs" / "bg.out"
    bg_log.parent.mkdir(parents=True, exist_ok=True)
    with open(bg_log, "a", encoding="utf-8", errors="replace") as out:
        proc = subprocess.Popen(
            args, start_new_session=True, stdin=subprocess.DEVNULL,
            stdout=out, stderr=subprocess.STDOUT,
        )
    (manifest.box_path / "run.pid").write_text(str(proc.pid), encoding="utf-8")
    console.print(
        f"[green]✓[/green] 后台启动 {slug} pid={proc.pid}"
        f"(exebox ps 查看;输出追加于 {_short(bg_log)})"
    )


@app.command("ps")
def ps_cmd() -> None:
    """列出后台启动且仍在运行的程序。"""
    import os

    store = RegistryStore(Config.from_env().library_root)
    rows = []
    for m in store.games().values():
        pid_file = m.box_path / "run.pid"
        if not pid_file.is_file():
            continue
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        alive = os.path.isdir(f"/proc/{pid}")
        rows.append((m.slug, pid, alive))
    if not rows:
        console.print("[dim]没有后台运行的程序[/dim]")
        return
    table = Table(title=None, box=None, pad_edge=False)
    table.add_column("SLUG", style="cyan")
    table.add_column("PID")
    table.add_column("STATE")
    for slug, pid, alive in rows:
        table.add_row(slug, str(pid), _ok(alive) if alive else "[dim]已退出[/dim]")
    console.print(table)
    console.print("[dim]杀掉:kill <PID>(exebox 的信号转发会收割整棵进程树)[/dim]")


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
    for w in manifest.warnings:
        console.print(f"  [yellow]⚠ {w}[/yellow]")
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
    """全局兜底:任何 ExeboxError 一行人话收场,绝不让 traceback 见人。"""
    try:
        app()
    except typer.Exit:
        raise
    except ExeboxError as e:
        err_console.print(f"[red]✗[/red] {e}")
        raise SystemExit(1) from e
    except KeyboardInterrupt:
        err_console.print("[yellow]已取消[/yellow]")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
