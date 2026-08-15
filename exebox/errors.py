"""exebox 异常层级。

约定:所有错误都携带"人话 + 建议动作",CLI 层捕获后原样打印;
core 内部禁止 print(CLI/GUI 共用,见 design §2.3)。
"""


class ExeboxError(Exception):
    """所有 exebox 错误的基类。"""


# ---- 清单 ----
class ManifestError(ExeboxError):
    """清单解析/校验失败。"""


class ManifestNotFoundError(ManifestError):
    """找不到清单文件。"""


# ---- 引擎(Proton)----
class ProtonError(ExeboxError):
    """Proton 相关错误基类。"""


class ProtonNotFoundError(ProtonError):
    """按名称找不到已安装的 Proton。"""


class NoProtonFoundError(ProtonError):
    """本机一个 Proton 都没发现。"""


# ---- prefix ----
class PrefixError(ExeboxError):
    """prefix 结构/操作错误。"""


class PrefixVersionError(PrefixError):
    """版本棘轮不匹配(升级不可逆,需显式确认)。"""


# ---- 启动 ----
class LaunchError(ExeboxError):
    """启动失败。"""


class SubreaperError(LaunchError):
    """prctl(PR_SET_CHILD_SUBREAPER) 失败(会降级,不致命)。"""


class ProcessError(LaunchError):
    """进程树管理问题。"""


# ---- 安装 ----
class InstallError(ExeboxError):
    """安装流程失败。"""


class StepExecutionError(InstallError):
    """某个 install step 失败。"""


# ---- 注册表缓存 ----
class RegistryError(ExeboxError):
    """registry.json 读写失败。"""
