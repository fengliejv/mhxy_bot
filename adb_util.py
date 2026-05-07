import os
import subprocess
from typing import Optional, Sequence

import cv2
import numpy as np
from PIL import Image
import io

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

    def screenshot_bgr(self) -> np.ndarray:
        png = self.screenshot_png()
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

    def tap(self, x: int, y: int) -> None:
        x = str(int(x))
        y = str(int(y))
        cp = self._run(["shell", "input", "swipe", x, y, x, y, "80"], timeout_s=10.0)
        if cp.returncode == 0:
            return
        cp2 = self._run(["shell", "input", "tap", x, y], timeout_s=10.0)
        if cp2.returncode != 0:
            err = (cp2.stderr or cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb tap 失败: rc={cp2.returncode} {err}".strip())

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

    def ime_set(self, ime_id: str) -> None:
        ime_id = str(ime_id or "").strip()
        if not ime_id:
            raise ValueError("ime_id 不能为空")
        cp = self._run(["shell", "ime", "set", ime_id], timeout_s=15.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb ime set 失败: rc={cp.returncode} {err}".strip())

    def adbkeyboard_input_text(self, text: str) -> None:
        msg = str(text)
        cp = self._run(["shell", "am", "broadcast", "-a", "ADB_INPUT_TEXT", "--es", "msg", msg], timeout_s=15.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adbkeyboard 输入失败: rc={cp.returncode} {err}".strip())

    def start_app(self, package: str, activity: str) -> None:
        cp = self._run(["shell", "am", "start", "-n", f"{package}/{activity}"], timeout_s=20.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb start app 失败: rc={cp.returncode} {err}".strip())

