import os
import threading
from typing import Iterable, Optional, Sequence, TypeVar

_lock = threading.Lock()
_dotenv_loaded = False
_dotenv_path = ".env"

T = TypeVar("T")


def init(dotenv_path: str = ".env") -> None:
    global _dotenv_loaded, _dotenv_path
    p = str(dotenv_path or ".env").strip() or ".env"
    if _dotenv_loaded and p == _dotenv_path:
        return
    with _lock:
        if _dotenv_loaded and p == _dotenv_path:
            return
        _dotenv_path = p
        _load_dotenv(p)
        _dotenv_loaded = True


def _load_dotenv(path: str) -> None:
    if not path:
        return
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def env_str(key: str, default: str = "") -> str:
    init()
    v = os.getenv(str(key), "")
    s = str(v or "").strip()
    if s:
        return s
    return str(default or "")


def env_optional_str(key: str) -> Optional[str]:
    init()
    s = str(os.getenv(str(key), "") or "").strip()
    return s or None


def env_str_first(keys: Sequence[str], default: str = "") -> str:
    for k in keys:
        v = env_str(str(k), "")
        if v:
            return v
    return str(default or "")


def env_int(key: str, default: int) -> int:
    s = env_str(key, "")
    if not s:
        return int(default)
    return int(s)


def env_float(key: str, default: float) -> float:
    s = env_str(key, "")
    if not s:
        return float(default)
    return float(s)


def env_bool(key: str, default: bool = False) -> bool:
    s = env_str(key, "")
    if not s:
        return bool(default)
    v = s.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def require_str(key: str) -> str:
    v = env_str(key, "")
    if not v:
        raise RuntimeError(f"缺少 {key}，请在环境变量或 .env 中配置")
    return v


def is_debug() -> bool:
    return env_bool("DEBUG", default=False)


def environ_copy() -> dict:
    init()
    return dict(os.environ)
