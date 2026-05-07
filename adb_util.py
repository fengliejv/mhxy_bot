import os
import subprocess
from typing import Optional, Sequence

import cv2
import numpy as np

import sys_util


def _adb_escape_text(text: str) -> str:
    s = str(text)
    s = s.replace(" ", "%s")
    escaped = []
    special = set("&|;<>()$`\\\"'*?![]{}")
    for ch in s:
        if ch in special:
            escaped.append("\\" + ch)
        else:
            escaped.append(ch)
    return "".join(escaped)


class AdbClient:
    def __init__(self, serial: Optional[str] = None, adb_path: Optional[str] = None) -> None:
        self.serial = serial or os.getenv("ADB_SERIAL", "").strip() or None
        self.adb_path = adb_path or os.getenv("ADB_PATH", "").strip() or "adb"

    def _base_cmd(self) -> list:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _run(self, args: Sequence[str], timeout_s: float = 15.0) -> subprocess.CompletedProcess:
        cmd = self._base_cmd() + list(args)
        return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)

    def screenshot_png(self) -> bytes:
        cp = self._run(["exec-out", "screencap", "-p"], timeout_s=30.0)
        if cp.returncode != 0 or not cp.stdout:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb screencap 失败: rc={cp.returncode} {err}".strip())
        data = cp.stdout
        if b"\r\n" in data:
            data = data.replace(b"\r\n", b"\n")
        sys_util.save_debug_image(data, "android_screencap")
        return data

    def screenshot_bgr(self) -> np.ndarray:
        png = self.screenshot_png()
        buf = np.frombuffer(png, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("截图解码失败")
        return img

    def tap(self, x: int, y: int) -> None:
        cp = self._run(["shell", "input", "tap", str(int(x)), str(int(y))], timeout_s=10.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb tap 失败: rc={cp.returncode} {err}".strip())

    def keyevent(self, keycode: int) -> None:
        cp = self._run(["shell", "input", "keyevent", str(int(keycode))], timeout_s=10.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb keyevent 失败: rc={cp.returncode} {err}".strip())

    def input_text(self, text: str) -> None:
        payload = _adb_escape_text(text)
        cp = self._run(["shell", "input", "text", payload], timeout_s=15.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb input text 失败: rc={cp.returncode} {err}".strip())

    def start_app(self, package: str, activity: str) -> None:
        cp = self._run(["shell", "am", "start", "-n", f"{package}/{activity}"], timeout_s=20.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb start app 失败: rc={cp.returncode} {err}".strip())

