import os
import time
from typing import Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

import sys_util
from adb_util import AdbClient
from android_bot import AndroidMhxyBot
from mhxy_app import MhxyAppController
from shimen_bot import _parse_ratio_roi, _roi_from_ratio


class MhxyAuth:
    def __init__(self, adb: Optional[AdbClient] = None, bot: Optional[AndroidMhxyBot] = None) -> None:
        self.adb = adb or AdbClient()
        self.bot = bot or AndroidMhxyBot(adb=self.adb)
        self.app = MhxyAppController(adb=self.adb)

        self.server_name = os.getenv("MHXY_SERVER_NAME", "乘风破浪").strip() or "乘风破浪"

        self.use_vl = (os.getenv("MHXY_AUTH_USE_VL", "1").strip() or "1").lower() in ("1", "true", "yes")
        self.step_sleep_s = float(os.getenv("MHXY_AUTH_STEP_SLEEP_S", "0.6") or "0.6")
        self.login_timeout_s = float(os.getenv("MHXY_AUTH_LOGIN_TIMEOUT_S", "600") or "600")
        self.logout_timeout_s = float(os.getenv("MHXY_AUTH_LOGOUT_TIMEOUT_S", "240") or "240")

        self.tpl_system_button = os.getenv("ANDROID_TPL_SYSTEM_BUTTON", "assets/android/system/system_button.png").strip() or "assets/android/system/system_button.png"
        self.thr_system_button = float(os.getenv("ANDROID_THR_SYSTEM_BUTTON", "0.68") or "0.68")
        self.thr_system_button_logout = float(os.getenv("ANDROID_THR_SYSTEM_BUTTON_LOGOUT", "0.52") or "0.52")
        self.tpl_exit_confirm = os.getenv("ANDROID_TPL_EXIT_CONFIRM", "assets/android/system/exit_confirm.png").strip() or "assets/android/system/exit_confirm.png"
        self.thr_exit_confirm = float(os.getenv("ANDROID_THR_EXIT_CONFIRM", "0.62") or "0.62")
        self.tpl_task_button = os.getenv("ANDROID_TPL_TASK_BUTTON", "assets/android/task/task_button.png").strip() or "assets/android/task/task_button.png"
        self.thr_task_button = float(os.getenv("ANDROID_THR_TASK_BUTTON", "0.62") or "0.62")
        self.tpl_server_target = os.getenv("ANDROID_TPL_SERVER_TARGET", "assets/android/auth/server_chengfengpolang.png").strip() or "assets/android/auth/server_chengfengpolang.png"
        self.thr_server_target = float(os.getenv("ANDROID_THR_SERVER_TARGET", "0.70") or "0.70")
        self.tpl_have_roles_btn = os.getenv("ANDROID_TPL_HAVE_ROLES_BTN", "assets/android/auth/btn_have_roles_screen.png").strip() or "assets/android/auth/btn_have_roles_screen.png"
        self.thr_have_roles_btn = float(os.getenv("ANDROID_THR_HAVE_ROLES_BTN", "0.62") or "0.62")
        self.tpl_enter_game_btn = os.getenv("ANDROID_TPL_ENTER_GAME_BTN", "assets/android/auth/btn_enter_game.png").strip() or "assets/android/auth/btn_enter_game.png"
        self.thr_enter_game_btn = float(os.getenv("ANDROID_THR_ENTER_GAME_BTN", "0.65") or "0.65")
        self.tpl_popup_ok = os.getenv("ANDROID_TPL_POPUP_OK", "assets/android/auth/popup_ok.png").strip() or "assets/android/auth/popup_ok.png"
        self.thr_popup_ok = float(os.getenv("ANDROID_THR_POPUP_OK", "0.70") or "0.70")
        self.tpl_confirm_btn = os.getenv("ANDROID_TPL_CONFIRM_BTN", "assets/android/keyboard/confirm.png").strip() or "assets/android/keyboard/confirm.png"
        self.thr_confirm_btn = float(os.getenv("ANDROID_THR_CONFIRM_BTN", "0.68") or "0.68")

        self.task_button_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_TASK_BUTTON_ROI_RATIO", "").strip()) or (0.80, 0.14, 0.995, 0.30)
        self.bottom_bar_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_BOTTOM_BAR_ROI_RATIO", "").strip()) or (0.20, 0.82, 0.90, 0.995)

    def _in_game(self) -> bool:
        try:
            r = self.bot.detect_coord_by_roi()
            if r.get("coord") is not None:
                return True
        except Exception:
            pass
        try:
            img = self.bot.screenshot_bgr()
            h, w = img.shape[:2]
            roi_btn = (int(w * 0.25), int(h * 0.40), int(w * 0.75), int(h * 0.92))
            if self._locate_template(img, self.tpl_enter_game_btn, roi=roi_btn, threshold=float(self.thr_enter_game_btn)) is not None:
                return False
            roi_left = (int(w * 0.05), int(h * 0.08), int(w * 0.40), int(h * 0.45))
            if self._locate_template(img, self.tpl_have_roles_btn, roi=roi_left, threshold=float(self.thr_have_roles_btn)) is not None:
                return False
            roi_bottom = _roi_from_ratio(img, self.bottom_bar_roi_ratio)
            return self._locate_template(img, self.tpl_system_button, roi=roi_bottom, threshold=float(self.thr_system_button_logout)) is not None
        except Exception:
            return False

    def _locate_template(
        self,
        img_bgr: np.ndarray,
        tpl_path: str,
        roi: Optional[Tuple[int, int, int, int]] = None,
        threshold: float = 0.75,
        tap_pos: Tuple[float, float] = (0.5, 0.5),
    ) -> Optional[Dict]:
        img = img_bgr
        src = img
        ox = 0
        oy = 0
        if roi is not None:
            x1, y1, x2, y2 = roi
            src = img[y1:y2, x1:x2].copy()
            ox, oy = x1, y1
        tpl = cv2.imread(tpl_path)
        if tpl is None:
            return None
        sh, sw = src.shape[:2]
        th, tw = tpl.shape[:2]
        if sh < th or sw < tw:
            return None
        res = cv2.matchTemplate(src, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if float(mx) < float(threshold):
            return None
        px = float(tap_pos[0])
        py = float(tap_pos[1])
        px = 0.5 if not (0.0 <= px <= 1.0) else px
        py = 0.5 if not (0.0 <= py <= 1.0) else py
        cx = int(ox + loc[0] + tw * px)
        cy = int(oy + loc[1] + th * py)
        return {"template": tpl_path, "confidence": float(mx), "point": (cx, cy), "roi": list(roi) if roi is not None else None}

    def _tap_by_template(
        self,
        tpl_path: str,
        roi: Optional[Tuple[int, int, int, int]] = None,
        threshold: float = 0.75,
        sleep_after: Optional[float] = None,
        tap_pos: Tuple[float, float] = (0.5, 0.5),
    ) -> Optional[Dict]:
        img = self.bot.screenshot_bgr()
        loc = self._locate_template(img, tpl_path, roi=roi, threshold=threshold, tap_pos=tap_pos)
        if loc is None:
            return None
        cx, cy = loc["point"]
        self.adb.tap(cx, cy)
        time.sleep(self.step_sleep_s if sleep_after is None else float(sleep_after))
        loc["tap"] = (cx, cy)
        del loc["point"]
        return loc

    def _tap_by_text(self, texts: Sequence[str], roi: Optional[Tuple[int, int, int, int]] = None, sleep_after: Optional[float] = None) -> Optional[Dict]:
        if not self.use_vl:
            return None
        import vl_locator

        img = self.bot.screenshot_bgr()
        for t in texts:
            try:
                loc = vl_locator.locate_text_center(img, str(t), roi=roi)
            except Exception:
                loc = None
            if loc is None:
                continue
            x = int(loc["x"])
            y = int(loc["y"])
            self.adb.tap(x, y)
            time.sleep(self.step_sleep_s if sleep_after is None else float(sleep_after))
            return {"text": str(t), "tap": (x, y), "located": loc, "roi": list(roi) if roi is not None else None}
        return None

    def _locate_text(self, img_bgr: np.ndarray, texts: Sequence[str], roi: Optional[Tuple[int, int, int, int]] = None) -> Optional[Dict]:
        if not self.use_vl:
            return None
        import vl_locator

        for t in texts:
            try:
                loc = vl_locator.locate_text_center(img_bgr, str(t), roi=roi)
            except Exception:
                loc = None
            if loc is None:
                continue
            return {"text": str(t), "located": loc, "roi": list(roi) if roi is not None else None}
        return None

    def _is_logged_out_screen(self, img_bgr: np.ndarray) -> bool:
        h, w = img_bgr.shape[:2]
        roi_btn = (int(w * 0.25), int(h * 0.40), int(w * 0.75), int(h * 0.92))
        thr_entry = max(0.90, float(self.thr_enter_game_btn))
        if self._locate_template(img_bgr, self.tpl_enter_game_btn, roi=roi_btn, threshold=thr_entry) is not None:
            return True
        return False

    def _handle_common_popups_once(self, include_cancel: bool = True) -> Optional[Dict]:
        img = self.bot.screenshot_bgr()
        h, w = img.shape[:2]
        roi_center = (int(w * 0.20), int(h * 0.12), int(w * 0.80), int(h * 0.92))
        roi_bottom = (int(w * 0.20), int(h * 0.60), int(w * 0.80), h)
        a = self._tap_by_template(self.tpl_popup_ok, roi=roi_center, threshold=float(self.thr_popup_ok), sleep_after=0.8)
        if a is None:
            a = self._tap_by_template(self.tpl_confirm_btn, roi=roi_center, threshold=float(self.thr_confirm_btn), sleep_after=0.8)
        if a is None:
            a = self._tap_by_template(self.tpl_popup_ok, roi=roi_bottom, threshold=float(self.thr_popup_ok), sleep_after=0.8)
        if a is None:
            a = self._tap_by_template(self.tpl_confirm_btn, roi=roi_bottom, threshold=float(self.thr_confirm_btn), sleep_after=0.8)
        if a is not None:
            return {"template_confirm": a}
        texts = ["同意", "允许", "确定", "确认", "继续", "我知道了", "下一步", "开始", "进入", "关闭"]
        if include_cancel:
            texts.append("取消")
        return self._tap_by_text(
            texts,
            roi=roi_center,
            sleep_after=0.8,
        ) or self._tap_by_text(["确定", "确认", "继续", "同意", "允许"], roi=roi_bottom, sleep_after=0.8)

    def ensure_logged_in(self, server_name: Optional[str] = None) -> Dict:
        sys_util.load_dotenv()
        srv = str(server_name or self.server_name).strip() or self.server_name
        start = self.app.ensure_started()

        deadline = time.time() + max(10.0, float(self.login_timeout_s))
        actions = [{"action": "ensure_started", "result": start}]

        while time.time() < deadline:
            a = self._handle_common_popups_once(include_cancel=False)
            if a is not None:
                actions.append({"action": "popup", "detail": a})
                continue
            if self._in_game():
                self.adb.screenshot_png()
                return {"ok": True, "reason": "already_in_game", "server": srv, "actions": actions}

            img = self.bot.screenshot_bgr()
            h, w = img.shape[:2]
            roi_btn = (int(w * 0.25), int(h * 0.40), int(w * 0.75), int(h * 0.92))
            a = self._tap_by_template(self.tpl_enter_game_btn, roi=roi_btn, threshold=float(self.thr_enter_game_btn), sleep_after=1.2)
            if a is not None:
                actions.append({"action": "tap_entry_tpl", "detail": a})
                continue
            a = self._tap_by_text(["进入游戏", "开始游戏", "点击进入", "开始", "进入"], roi=roi_btn, sleep_after=1.2)
            if a is not None:
                actions.append({"action": "tap_entry", "detail": a})
                continue

            roi_srv = (int(w * 0.10), int(h * 0.12), int(w * 0.92), int(h * 0.92))
            a = self._tap_by_text([srv], roi=roi_srv, sleep_after=1.0)
            if a is not None:
                actions.append({"action": "tap_server", "detail": a})
                continue
            a = self._tap_by_template(self.tpl_server_target, roi=roi_srv, threshold=float(self.thr_server_target), sleep_after=1.0)
            if a is not None:
                actions.append({"action": "tap_server_tpl", "detail": a})
                continue

            roi_left = (int(w * 0.05), int(h * 0.12), int(w * 0.28), int(h * 0.55))
            a = self._tap_by_text(["已有角色"], roi=roi_left, sleep_after=0.8)
            if a is not None:
                actions.append({"action": "open_have_roles", "detail": a})
                continue
            a = self._tap_by_template(self.tpl_have_roles_btn, roi=roi_left, threshold=float(self.thr_have_roles_btn), sleep_after=0.8, tap_pos=(0.50, 0.35))
            if a is not None:
                actions.append({"action": "open_have_roles_tpl", "detail": a})
                continue
            self.adb.tap(int(w * 0.16), int(h * 0.19))
            time.sleep(0.5)
            actions.append({"action": "tap_have_roles_fallback"})
            continue

            a = self._tap_by_text(["选择服务器", "服务器", "切换服务器"], roi=roi_srv, sleep_after=1.0)
            if a is not None:
                actions.append({"action": "open_server", "detail": a})
                continue

            roi_role = (int(w * 0.55), int(h * 0.55), w, h)
            a = self._tap_by_text(["进入游戏", "进入", "开始游戏"], roi=roi_role, sleep_after=2.0)
            if a is not None:
                actions.append({"action": "enter_role", "detail": a})
                continue

            time.sleep(1.2)
            actions.append({"action": "wait"})

        self.adb.screenshot_png()
        return {"ok": False, "reason": "login_timeout", "server": srv, "actions": actions}

    def ensure_logged_out(self) -> Dict:
        sys_util.load_dotenv()
        deadline = time.time() + max(10.0, float(self.logout_timeout_s))
        actions = []

        while time.time() < deadline:
            img0 = self.bot.screenshot_bgr()
            if self._is_logged_out_screen(img0):
                self.adb.screenshot_png()
                return {"ok": True, "reason": "logged_out", "actions": actions}

            img = img0
            h0, w0 = img.shape[:2]
            roi_confirm = (int(w0 * 0.30), int(h0 * 0.40), int(w0 * 0.90), int(h0 * 0.86))
            a = self._tap_by_template(
                self.tpl_exit_confirm,
                roi=roi_confirm,
                threshold=float(self.thr_exit_confirm),
                sleep_after=1.2,
                tap_pos=(0.55, 0.30),
            )
            if a is None:
                a = self._tap_by_text(["确认", "确定"], roi=roi_confirm, sleep_after=1.2)
            if a is not None:
                actions.append({"action": "confirm_exit", "detail": a})
                time.sleep(1.5)
                if not self.app.is_running():
                    self.adb.screenshot_png()
                    return {"ok": True, "reason": "logged_out", "actions": actions}
                continue
            roi_bottom = _roi_from_ratio(img, self.bottom_bar_roi_ratio)
            a = self._tap_by_template(self.tpl_system_button, roi=roi_bottom, threshold=float(self.thr_system_button_logout), sleep_after=0.8)
            if a is None:
                a = self._tap_by_text(["系统"], roi=roi_bottom, sleep_after=0.8)
            if a is not None:
                actions.append({"action": "open_system", "detail": a})

            img2 = self.bot.screenshot_bgr()
            h, w = img2.shape[:2]
            roi_menu = (int(w * 0.12), int(h * 0.10), int(w * 0.90), int(h * 0.95))
            roi_exit = (int(w * 0.65), int(h * 0.70), int(w * 0.98), int(h * 0.98))
            a = self._tap_by_text(["退出游戏"], roi=roi_exit, sleep_after=0.8)
            if a is not None:
                actions.append({"action": "tap_exit_game", "detail": a})
                _ = self._tap_by_text(["确定", "确认", "同意"], roi=(int(w * 0.28), int(h * 0.70), int(w * 0.72), h), sleep_after=1.2)
                time.sleep(1.2)
                continue

            a = self._tap_by_text(["退出登录", "切换账号", "返回登录", "退出"], roi=roi_menu, sleep_after=0.8)
            if a is not None:
                actions.append({"action": "tap_logout", "detail": a})
                _ = self._tap_by_text(["确定", "确认", "同意"], roi=(int(w * 0.28), int(h * 0.70), int(w * 0.72), h), sleep_after=1.2)
                time.sleep(1.2)
                continue

            a = self._handle_common_popups_once(include_cancel=False)
            if a is not None:
                actions.append({"action": "popup", "detail": a})
                continue

            self.adb.keyevent(4)
            time.sleep(0.6)
            actions.append({"action": "back"})

        self.adb.screenshot_png()
        return {"ok": False, "reason": "logout_timeout", "actions": actions}
