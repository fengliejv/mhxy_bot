import subprocess
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image
import io

import botconfig
import sys_util

_ADB_PATH: Optional[str] = None
_ADB_SERIAL: Optional[str] = None


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
    resolved_adb_path = str(adb_path or botconfig.ADB_PATH or "adb").strip() or "adb"
    env_serial = botconfig.ADB_SERIAL
    resolved_serial = str(serial or env_serial or "").strip() or None
    if resolved_serial is None:
        resolved_serial = _auto_pick_serial(resolved_adb_path)
    _ADB_PATH = resolved_adb_path
    _ADB_SERIAL = resolved_serial
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


def screenshot_png() -> bytes:
    cp = _run_checked(["exec-out", "screencap", "-p"], "adb screencap", timeout_s=30.0)
    if not cp.stdout:
        raise RuntimeError("adb screencap 失败: 空输出")
    data = cp.stdout
    sig = b"\x89PNG\r\n\x1a\n"
    if not data.startswith(sig):
        if b"\x89PNG" in data:
            data = data[data.find(b"\x89PNG") :]
        if not data.startswith(sig):
            fixed = data.replace(b"\r\r\n", b"\n")
            if fixed.startswith(sig):
                data = fixed
    sys_util.save_debug_image(data, "android_screencap")
    return data


def screenshot_bgr() -> np.ndarray:
    png = screenshot_png()
    buf = np.frombuffer(png, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        try:
            pil_img = Image.open(io.BytesIO(png))
            pil_img = pil_img.convert("RGB")
            rgb = np.array(pil_img)
            img = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            img = None
    if img is None:
        raise RuntimeError("截图解码失败")
    return img


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


def adbkeyboard_input_text(text: str) -> None:
    msg = str(text)
    _run_checked(["shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", msg], "adbkeyboard 输入", timeout_s=15.0)
