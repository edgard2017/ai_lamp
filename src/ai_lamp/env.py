"""零依赖的 .env 加载器（项目启动时自动读取密钥/配置）。

从仓库根目录找 `.env`，把 KEY=VALUE 逐行读进 os.environ。
**不覆盖**已经在真实环境里 export 的变量——即真实环境优先，.env 兜底。
这样个人机上填一次 .env 就够，而 CI/临时覆盖仍可用 export。

.env 已被 .gitignore 忽略，不会上传。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _repo_root() -> Path:
    # src/ai_lamp/env.py -> ai_lamp -> src -> <repo root>
    return Path(__file__).resolve().parents[2]


def find_dotenv(filename: str = ".env") -> Optional[Path]:
    """在仓库根目录和当前工作目录找 .env，返回第一个存在的路径。"""
    for base in (_repo_root(), Path.cwd()):
        candidate = base / filename
        if candidate.is_file():
            return candidate
    return None


def load_env(path: Optional[str] = None, override: bool = False) -> bool:
    """加载 .env 到 os.environ；成功读到文件返回 True，否则 False（不报错）。

    override=False（默认）时，已存在于环境里的变量不被覆盖。
    """
    target = Path(path) if path else find_dotenv()
    if target is None or not target.is_file():
        return False

    for raw in target.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = val
    return True
