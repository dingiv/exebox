"""doctor:箱体检(core 纯检查,CLI 渲染)。

设计约束:只诊断与建议,绝不自动修改(零隐藏参数哲学);
status:ok / warn / fail;fail 使 CLI 退出码非零。
"""

import os
from dataclasses import dataclass

from exebox.errors import ExeboxError
from exebox.models import GameManifest
from exebox.prefix import manager
from exebox.proton.resolver import ProtonResolver


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # "ok" | "warn" | "fail"
    detail: str
    suggestion: str = ""


def diagnose(manifest: GameManifest, resolver: ProtonResolver | None = None) -> list[CheckResult]:
    resolver = resolver or ProtonResolver()
    out: list[CheckResult] = []

    # 1/2 exe 与 cwd
    if manifest.exe.is_file():
        out.append(CheckResult("exe", "ok", str(manifest.exe)))
    else:
        out.append(CheckResult(
            "exe", "fail", f"不存在: {manifest.exe}",
            "检查清单 exe 字段;安装器流程没跑过的话先 exebox install",
        ))
    if manifest.game_dir.is_dir():
        out.append(CheckResult("cwd", "ok", str(manifest.game_dir)))
    else:
        out.append(CheckResult(
            "cwd", "fail", f"game_dir 不存在: {manifest.game_dir}",
            "cwd 契约要求启动前就位(见 design §6.2)",
        ))

    # 3 引擎
    try:
        pv = resolver.resolve(manifest.proton)
        out.append(CheckResult("proton", "ok", f"{pv.name} ({pv.version_str})"))
        # 5 版本棘轮
        verdict = manager.check_version(manifest.prefix, pv)
        mapping = {
            "match": ("prefix-version", "ok", "与目标引擎一致"),
            "no_prefix": ("prefix-version", "warn", "尚无 version 文件(全新 prefix,首启创建)",
                          "正常现象,首次启动稍慢"),
            "upgrade_needed": (
                "prefix-version", "warn", "与目标引擎不一致 —— 启动将触发不可逆升级",
                "确有需要就 launch 时确认;想换回旧引擎请先备份 prefix",
            ),
            "unknown": ("prefix-version", "warn", "无法确定目标引擎的 prefix 版本",
                        "该 Proton 脚本缺 CURRENT_PREFIX_VERSION,跳过棘轮检查"),
        }
        name, status, detail = mapping[verdict][:3]
        out.append(CheckResult(name, status, detail, mapping[verdict][3] if len(mapping[verdict]) > 3 else ""))
    except ExeboxError as e:
        out.append(CheckResult(
            "proton", "fail", str(e),
            "exebox list --protons 查看本机可用引擎后修改清单 proton 字段",
        ))

    # 4/6 prefix 形态
    if manifest.prefix.exists():
        managed = "Steam 托管(只读策略)" if manager.is_managed(manifest.prefix) else "自建"
        out.append(CheckResult("prefix", "ok", f"{manifest.prefix} [{managed}]"))
    else:
        out.append(CheckResult("prefix", "warn", f"不存在: {manifest.prefix}",
                               "首次 launch 会自动创建"))

    # 7 陈旧 run.pid
    pid_file = manifest.box_path / "run.pid"
    if pid_file.is_file():
        pid = int(pid_file.read_text(encoding="utf-8").strip())
        if os.path.isdir(f"/proc/{pid}"):
            out.append(CheckResult("running", "ok", f"后台运行中 pid={pid}",
                                   "exebox ps 查看;kill 该 pid 整树收割"))
        else:
            out.append(CheckResult("running", "warn", f"run.pid 指向已死进程 {pid}",
                                   f"rm {pid_file}"))

    # 8 路径告警
    for w in manifest.warnings:
        out.append(CheckResult("path", "warn", w, "通常无碍;报错时优先怀疑这里"))

    # 9 安装步骤引用
    if manifest.install:
        for i, step in enumerate(manifest.install.steps):
            if step.type == "copy" and step.src and not step.src.exists():
                out.append(CheckResult(
                    f"step[{i}]", "warn", f"copy 的 src 不存在: {step.src}",
                    "重装或修正 install.steps",
                ))

    # 10 箱可写
    if manifest.box_path.is_dir() and os.access(manifest.box_path, os.W_OK):
        out.append(CheckResult("box", "ok", f"可写: {manifest.box_path}"))
    else:
        out.append(CheckResult("box", "fail", f"不可写: {manifest.box_path}",
                               "检查目录权限"))

    return out


def worst_status(results: list[CheckResult]) -> str:
    if any(r.status == "fail" for r in results):
        return "fail"
    if any(r.status == "warn" for r in results):
        return "warn"
    return "ok"
