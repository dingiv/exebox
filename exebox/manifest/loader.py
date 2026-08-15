"""清单(game.yaml)加载与校验。

原则(design §3.1 / 零隐藏参数):
- 未知字段 = 错误(拼错键名必须炸,绝不静默忽略)
- 路径在加载期全部解析为绝对 Path
- 存在性不做硬校验(health check 负责),仅结构性错误抛 ManifestError

路径解析规则:
- exe:相对则基于 game_dir;绝对则直接用
- game_dir / prefix / install.source:相对则基于箱根(清单所在目录)
- game_dir 缺省:要求 exe 为绝对路径,默认取 exe.parent
"""

from pathlib import Path

import yaml

from exebox.errors import ManifestError, ManifestNotFoundError
from exebox.models import GameManifest, InstallConfig, InstallStep

MANIFEST_FILENAME = "game.yaml"

_ROOT_KEYS = {
    "name", "exe", "proton", "prefix", "game_dir", "env", "dll_overrides",
    "args", "game_id", "path_append", "verb", "notes", "install",
}
_INSTALL_KEYS = {"source", "steps"}
_STEP_KEYS = {
    "description", "type", "command", "key", "value", "value_type",
    "reg_hive", "reg_arch", "src", "dst",
}
_DEFAULT_PROTON = "Proton - Experimental"


def load(path: Path) -> GameManifest:
    """加载并校验一份清单。path 指向 game.yaml 文件本身。"""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ManifestNotFoundError(f"清单不存在: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ManifestError(f"清单不可读: {path}\n{e}") from e
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ManifestError(f"YAML 语法错误: {path}\n{e}") from e
    if not isinstance(raw, dict):
        raise ManifestError(f"清单必须是映射(dict): {path}")

    unknown = set(raw) - _ROOT_KEYS
    if unknown:
        raise ManifestError(
            f"清单 {path.name} 含未知字段: {sorted(unknown)};"
            f"合法字段: {sorted(_ROOT_KEYS)}(拼错键名是错误,不是风格问题)"
        )

    box_path = path.parent
    slug = box_path.name

    if "exe" not in raw:
        raise ManifestError(f"清单 {path.name} 缺必填字段 'exe'")

    game_dir = _resolve_against(box_path, raw.get("game_dir")) if raw.get("game_dir") else None
    exe_raw = str(raw["exe"])
    if Path(exe_raw).is_absolute():
        exe = Path(exe_raw)
        game_dir = game_dir or exe.parent
    else:
        if game_dir is None:
            raise ManifestError(
                f"清单 {path.name}: exe 为相对路径时必须显式给出 game_dir"
                f"(cwd 契约:绝不猜测,见 design §6.2)"
            )
        exe = game_dir / exe_raw

    prefix = (
        _resolve_against(box_path, raw["prefix"])
        if raw.get("prefix")
        else box_path / "prefix"
    )

    env = _check_str_map(raw.get("env"), "env", path)
    dll_overrides = str(raw.get("dll_overrides", "") or "")

    args = raw.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ManifestError(f"清单 {path.name}: 'args' 必须是字符串列表")

    game_id = raw.get("game_id", 0)
    if not isinstance(game_id, int) or isinstance(game_id, bool) or game_id < 0:
        raise ManifestError(f"清单 {path.name}: 'game_id' 必须是非负整数")

    path_append_raw = raw.get("path_append", [])
    if not isinstance(path_append_raw, list):
        raise ManifestError(f"清单 {path.name}: 'path_append' 必须是列表")
    path_append = [_resolve_against(box_path, p) for p in path_append_raw]

    verb = str(raw.get("verb", "run"))

    install = _load_install(raw.get("install"), box_path, path)

    return GameManifest(
        name=str(raw.get("name") or slug),
        exe=exe,
        proton=str(raw.get("proton") or _DEFAULT_PROTON),
        prefix=prefix,
        game_dir=game_dir,
        env=env,
        dll_overrides=dll_overrides,
        args=list(args),
        game_id=game_id,
        path_append=path_append,
        verb=verb,
        notes=str(raw.get("notes", "") or ""),
        install=install,
        box_path=box_path,
        slug=slug,
    )


def load_box(box_path: Path) -> GameManifest:
    """按箱目录加载其 game.yaml。"""
    return load(Path(box_path) / MANIFEST_FILENAME)


def _resolve_against(base: Path, value) -> Path:
    p = Path(str(value)).expanduser()
    return p if p.is_absolute() else base / p


def _check_str_map(value, field: str, path: Path) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or not all(
        isinstance(k, str) and isinstance(v, (str, int, float, bool))
        for k, v in value.items()
    ):
        raise ManifestError(
            f"清单 {path.name}: '{field}' 必须是 str->标量 的映射"
        )
    return {k: str(v) for k, v in value.items()}


def _load_install(raw_install, box_path: Path, path: Path) -> InstallConfig | None:
    if raw_install is None:
        return None
    if not isinstance(raw_install, dict):
        raise ManifestError(f"清单 {path.name}: 'install' 必须是映射")
    unknown = set(raw_install) - _INSTALL_KEYS
    if unknown:
        raise ManifestError(
            f"清单 {path.name} install 段含未知字段: {sorted(unknown)}"
        )
    if "source" not in raw_install:
        raise ManifestError(f"清单 {path.name}: install 段必须有 'source'")

    source = _resolve_against(box_path, raw_install["source"])
    steps_raw = raw_install.get("steps", [])
    if not isinstance(steps_raw, list):
        raise ManifestError(f"清单 {path.name}: install.steps 必须是列表")

    steps: list[InstallStep] = []
    for i, s in enumerate(steps_raw):
        steps.append(_load_step(s, i, box_path, path))
    return InstallConfig(source=source, steps=steps)


def _load_step(raw_step, index: int, box_path: Path, path: Path) -> InstallStep:
    if not isinstance(raw_step, dict):
        raise ManifestError(f"清单 {path.name}: install.steps[{index}] 必须是映射")
    unknown = set(raw_step) - _STEP_KEYS
    if unknown:
        raise ManifestError(
            f"清单 {path.name} install.steps[{index}] 含未知字段: {sorted(unknown)}"
        )
    stype = str(raw_step.get("type", ""))
    if stype not in InstallStep.STEP_TYPES:
        raise ManifestError(
            f"清单 {path.name} install.steps[{index}]: 不支持的 type '{stype}'"
            f"(合法: {list(InstallStep.STEP_TYPES)};winetricks 计划 v1.x 后评估)"
        )
    command = raw_step.get("command")
    if command is not None and (
        not isinstance(command, list) or not all(isinstance(c, str) for c in command)
    ):
        raise ManifestError(
            f"清单 {path.name} install.steps[{index}]: 'command' 必须是字符串列表"
        )
    return InstallStep(
        description=str(raw_step.get("description", f"step-{index}")),
        type=stype,
        command=list(command) if command else None,
        key=raw_step.get("key"),
        value=None if raw_step.get("value") is None else str(raw_step["value"]),
        value_type=raw_step.get("value_type"),
        reg_hive=raw_step.get("reg_hive"),
        reg_arch=raw_step.get("reg_arch"),
        src=_resolve_against(box_path, raw_step["src"]) if raw_step.get("src") else None,
        dst=_resolve_against(box_path, raw_step["dst"]) if raw_step.get("dst") else None,
    )
