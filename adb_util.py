import subprocess
from typing import Optional, Sequence

import cv2
import numpy as np
from PIL import Image
import io

import botconfig
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
        env_serial = botconfig.env_optional_str("ADB_SERIAL")
        resolved_adb_path = adb_path or botconfig.env_str("ADB_PATH", botconfig.ADB_PATH) or botconfig.ADB_PATH
        self.serial = serial or env_serial or self._auto_pick_serial(resolved_adb_path)
        self.adb_path = resolved_adb_path

    def _auto_pick_serial(self, adb_path: str) -> Optional[str]:
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

    def _restart_server(self) -> None:
        try:
            subprocess.run([self.adb_path, "kill-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
        except Exception:
            pass
        try:
            subprocess.run([self.adb_path, "start-server"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10.0)
        except Exception:
            pass

    def _base_cmd(self) -> list:
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd

    def _run(self, args: Sequence[str], timeout_s: float = 15.0) -> subprocess.CompletedProcess:
        cmd = self._base_cmd() + list(args)
        cp = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
        if cp.returncode == 0:
            return cp
        err_raw = (cp.stderr or b"").decode("utf-8", errors="replace")
        err = err_raw.lower()
        should_retry = ("device" in err and "not found" in err) or ("offline" in err) or ("no devices" in err)
        if should_retry:
            self._restart_server()
            self.serial = self._auto_pick_serial(self.adb_path)
            cmd2 = self._base_cmd() + list(args)
            cp2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
            if cp2.returncode == 0:
                return cp2
            if self.serial:
                self.serial = None
                cmd3 = self._base_cmd() + list(args)
                return subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout_s)
        return cp

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
        cp = self._run(["shell", "input", "tap", x, y], timeout_s=10.0)
        if cp.returncode == 0:
            return
        cp2 = self._run(["shell", "input", "swipe", x, y, x, y, "80"], timeout_s=10.0)
        if cp2.returncode != 0:
            err = (cp2.stderr or cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb tap 失败: rc={cp2.returncode} {err}".strip())

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        args = ["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms))]
        cp = self._run(args, timeout_s=15.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb swipe 失败: rc={cp.returncode} {err}".strip())

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

    def force_stop(self, package: str) -> None:
        pkg = str(package or "").strip()
        if not pkg:
            raise ValueError("package 不能为空")
        cp = self._run(["shell", "am", "force-stop", pkg], timeout_s=20.0)
        if cp.returncode != 0:
            err = (cp.stderr or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"adb force-stop 失败: rc={cp.returncode} {err}".strip())

    def shell(self, cmd: str, timeout_s: float = 20.0) -> str:
        s = str(cmd or "").strip()
        if not s:
            return ""
        cp = self._run(["shell", "sh", "-c", s], timeout_s=float(timeout_s))
        out = (cp.stdout or b"").decode("utf-8", errors="replace")
        return out

    def pidof(self, package: str) -> Optional[int]:
        pkg = str(package or "").strip()
        if not pkg:
            return None
        out = self.shell(f"pidof {pkg} 2>/dev/null || true", timeout_s=10.0).strip()
        nums = [x for x in out.split() if x.strip().isdigit()]
        return int(nums[0]) if nums else None

