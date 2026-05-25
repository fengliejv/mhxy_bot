import subprocess
import threading
from typing import Optional, Sequence, Tuple

try:
    import scrcpy
except Exception:
    scrcpy = None

import cv2
import numpy as np

from .core import config as botconfig
from .core import sys as sys_util

_ADB_PATH: Optional[str] = None
_ADB_SERIAL: Optional[str] = None
_SCRCPY_CLIENT = None
_SCRCPY_SERIAL: Optional[str] = None
_SCRCPY_LAST_FRAME: Optional[np.ndarray] = None
_SCRCPY_FRAME_LOCK = threading.Lock()
_SCRCPY_FRAME_READY = threading.Event()


def _auto_pick_serial(adb_path: str) -> Optional[str]:
    try:
        subprocess.run([adb_path, "start-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
        cp = subprocess.run([adb_path, "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
    except Exception:
        return None
    out = (cp.stdout or b"").decode("utf-8", errors="replace").splitlines()
    devices = []
    for line in out:
        s = line.strip()
        if not s or s.startswith("List of devices"):
            continue
        parts = s.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices[0] if len(devices) == 1 else None


def _restart_server(adb_path: str) -> None:
    try:
        subprocess.run([adb_path, "kill-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
    except Exception:
        pass
    try:
        subprocess.run([adb_path, "start-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
    except Exception:
        pass


def init_adb(serial: Optional[str] = None, adb_path: Optional[str] = None) -> Tuple[str, Optional[str]]:
    global _ADB_PATH, _ADB_SERIAL
    prev_adb_path = _ADB_PATH
    prev_serial = _ADB_SERIAL
    resolved_adb_path = str(adb_path or botconfig.ADB_PATH or "adb").strip() or "adb"
    env_serial = botconfig.ADB_SERIAL
    resolved_serial = str(serial or env_serial or "").strip() or None
    if resolved_serial is None:
        resolved_serial = _auto_pick_serial(resolved_adb_path)
    _ADB_PATH = resolved_adb_path
    _ADB_SERIAL = resolved_serial
    if prev_adb_path != resolved_adb_path or prev_serial != resolved_serial:
        _stop_scrcpy_client()
    return _ADB_PATH, _ADB_SERIAL


def _ensure_adb() -> Tuple[str, Optional[str]]:
    global _ADB_PATH, _ADB_SERIAL
    if not _ADB_PATH:
        return init_adb()
    return _ADB_PATH, _ADB_SERIAL


def _base_cmd() -> list:
    adb_path, serial = _ensure_adb()
    cmd = [adb_path]
    if serial:
        cmd += ["-s", serial]
    return cmd


def _run(args: Sequence[str], timeout_s: float = 15.0) -> subprocess.CompletedProcess:
    global _ADB_SERIAL
    cmd = _base_cmd() + list(args)
    cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
    if cp.returncode == 0:
        return cp
    err_raw = (cp.stderr or b"").decode("utf-8", errors="replace")
    err = err_raw.lower()
    should_retry = ("device" in err and "not found" in err) or ("offline" in err) or ("no devices" in err)
    if should_retry:
        adb_path, _ = _ensure_adb()
        _restart_server(adb_path)
        _ADB_SERIAL = _auto_pick_serial(adb_path)
        cmd2 = _base_cmd() + list(args)
        cp2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
        if cp2.returncode == 0:
            return cp2
        if _ADB_SERIAL:
            _ADB_SERIAL = None
            cmd3 = _base_cmd() + list(args)
            return subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
    return cp


def _stderr_text(cp: subprocess.CompletedProcess) -> str:
    return (cp.stderr or b"").decode("utf-8", errors="replace")


def _run_checked(args: Sequence[str], action: str, timeout_s: float = 15.0) -> subprocess.CompletedProcess:
    cp = _run(args, timeout_s=timeout_s)
    if cp.returncode != 0:
        raise RuntimeError(f"{action} 失败: rc={cp.returncode} {_stderr_text(cp)}".strip())
    return cp


def _screenshot_backend() -> str:
    backend = str(getattr(botconfig, "ANDROID_SCREENSHOT_BACKEND", "auto") or "auto").strip().lower()
    if backend == "adb":
        raise RuntimeError("截图后端已收紧为仅允许 scrcpy；请将 ANDROID_SCREENSHOT_BACKEND 改为 scrcpy 或 auto")
    if backend not in {"auto", "scrcpy"}:
        raise RuntimeError(f"不支持的截图后端: {backend}")
    return backend


def _stop_scrcpy_client() -> None:
    global _SCRCPY_CLIENT, _SCRCPY_SERIAL, _SCRCPY_LAST_FRAME
    with _SCRCPY_FRAME_LOCK:
        client = _SCRCPY_CLIENT
        _SCRCPY_CLIENT = None
        _SCRCPY_SERIAL = None
        _SCRCPY_LAST_FRAME = None
        _SCRCPY_FRAME_READY.clear()
    if client is not None:
        try:
            client.stop()
        except Exception:
            pass


def _on_scrcpy_frame(frame) -> None:
    global _SCRCPY_LAST_FRAME
    if frame is None:
        return
    with _SCRCPY_FRAME_LOCK:
        _SCRCPY_LAST_FRAME = frame.copy()
        _SCRCPY_FRAME_READY.set()


def _ensure_scrcpy_client():
    global _SCRCPY_CLIENT, _SCRCPY_SERIAL
    if scrcpy is None:
        raise RuntimeError("缺少 scrcpy 依赖，请先安装: pip install scrcpy-client")
    _, serial = _ensure_adb()
    with _SCRCPY_FRAME_LOCK:
        client = _SCRCPY_CLIENT
        if client is not None and _SCRCPY_SERIAL == serial and bool(getattr(client, "alive", False)):
            return client
    _stop_scrcpy_client()
    _SCRCPY_FRAME_READY.clear()
    client = scrcpy.Client(
        device=serial if serial else None,
        max_width=int(botconfig.ANDROID_SCRCPY_MAX_WIDTH),
        bitrate=int(botconfig.ANDROID_SCRCPY_BITRATE),
        max_fps=int(botconfig.ANDROID_SCRCPY_MAX_FPS),
        connection_timeout=int(botconfig.ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS),
    )
    client.add_listener(scrcpy.EVENT_FRAME, _on_scrcpy_frame)
    client.start(threaded=True)
    with _SCRCPY_FRAME_LOCK:
        _SCRCPY_CLIENT = client
        _SCRCPY_SERIAL = serial
    wait_timeout_s = max(2.0, float(botconfig.ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS) / 1000.0 + 1.0)
    if _SCRCPY_FRAME_READY.wait(timeout=wait_timeout_s):
        return client
    if getattr(client, "last_frame", None) is not None:
        _on_scrcpy_frame(client.last_frame)
        return client
    _stop_scrcpy_client()
    raise RuntimeError("scrcpy 启动成功但未收到首帧")


def _scrcpy_screenshot_bgr() -> np.ndarray:
    client = _ensure_scrcpy_client()
    frame = getattr(client, "last_frame", None)
    if frame is None:
        if not _SCRCPY_FRAME_READY.wait(timeout=1.0):
            raise RuntimeError("scrcpy 未返回视频帧")
        with _SCRCPY_FRAME_LOCK:
            frame = None if _SCRCPY_LAST_FRAME is None else _SCRCPY_LAST_FRAME.copy()
    else:
        frame = frame.copy()
    if frame is None:
        raise RuntimeError("scrcpy 视频帧为空")
    sys_util.save_debug_image(frame, "android_scrcpy")
    return frame


def _scrcpy_screenshot_png() -> bytes:
    img = _scrcpy_screenshot_bgr()
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise RuntimeError("scrcpy 截图转 PNG 失败")
    return bytes(buf)


def screenshot_png() -> bytes:
    _screenshot_backend()
    return _scrcpy_screenshot_png()


def screenshot_bgr() -> np.ndarray:
    _screenshot_backend()
    return _scrcpy_screenshot_bgr()


def tap(x: int, y: int) -> None:
    x = str(int(x))
    y = str(int(y))
    cp = _run(["shell", "input", "tap", x, y], timeout_s=10.0)
    if cp.returncode == 0:
        return
    cp2 = _run(["shell", "input", "swipe", x, y, x, y, "80"], timeout_s=10.0)
    if cp2.returncode != 0:
        err = _stderr_text(cp2) or _stderr_text(cp)
        raise RuntimeError(f"adb tap 失败: rc={cp2.returncode} {err}".strip())


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    args = ["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))]
    _run_checked(args, "adb swipe", timeout_s=15.0)


def ime_set(ime_id: str) -> None:
    ime_id = str(ime_id or "").strip()
    if not ime_id:
        raise ValueError("ime_id 不能为空")
    _run_checked(["shell", "ime", "set", ime_id], "adb ime set", timeout_s=15.0)


def ime_get_current() -> str:
    cp = _run(["shell", "settings", "get", "secure", "default_input_method"], timeout_s=15.0)
    if cp.returncode != 0:
        err = _stderr_text(cp)
        raise RuntimeError(f"获取当前输入法失败: rc={cp.returncode} {err}".strip())
    return ((cp.stdout or b"").decode("utf-8", errors="replace")).strip()


def adbkeyboard_input_text(text: str) -> None:
    msg = str(text)
    _run_checked(["shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", msg], "adbkeyboard 输入", timeout_s=15.0)
