import os
import time
from typing import Dict, Optional

from adb_util import AdbClient


class MhxyAppController:
    def __init__(self, adb: Optional[AdbClient] = None) -> None:
        self.adb = adb or AdbClient()
        self.package = os.getenv("MHXY_ANDROID_PACKAGE", "com.netease.mhxyhtb").strip() or "com.netease.mhxyhtb"
        self.activity = os.getenv("MHXY_ANDROID_ACTIVITY", "com.netease.game.MessiahNativeActivity").strip() or "com.netease.game.MessiahNativeActivity"

    def is_running(self) -> bool:
        return self.adb.pidof(self.package) is not None

    def start(self, wait_s: float = 8.0) -> Dict:
        self.adb.start_app(self.package, self.activity)
        time.sleep(max(0.0, float(wait_s)))
        return {"ok": True, "package": self.package, "activity": self.activity, "running": self.is_running()}

    def stop(self, wait_s: float = 1.0) -> Dict:
        self.adb.force_stop(self.package)
        time.sleep(max(0.0, float(wait_s)))
        return {"ok": True, "package": self.package, "running": self.is_running()}

    def ensure_started(self) -> Dict:
        if self.is_running():
            return {"ok": True, "running": True, "started": False}
        r = self.start(wait_s=float(os.getenv("MHXY_ANDROID_START_WAIT_S", "10") or "10"))
        return {"ok": True, "running": r.get("running"), "started": True, "start": r}
