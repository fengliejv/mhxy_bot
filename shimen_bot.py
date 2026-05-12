import argparse
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import sys_util
import siliflow_client
from android_bot import AndroidMhxyBot


def _parse_ratio_roi(text: str) -> Optional[Tuple[float, float, float, float]]:
    s = str(text or "").strip()
    if not s:
        return None
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(p) for p in parts]
    except Exception:
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _roi_from_ratio(img_bgr: np.ndarray, ratio_roi: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
    h, w = img_bgr.shape[:2]
    x1, y1, x2, y2 = ratio_roi
    ax1 = max(0, min(int(w * x1), w - 1))
    ax2 = max(ax1 + 1, min(int(w * x2), w))
    ay1 = max(0, min(int(h * y1), h - 1))
    ay2 = max(ay1 + 1, min(int(h * y2), h))
    return ax1, ay1, ax2, ay2


class ShimenTaskContext:
    def __init__(
        self,
        family: str = "unknown",
        task_kind: str = "",
        task_type: str = "",
        raw_text: str = "",
        objective_text: str = "",
        target_npc: str = "",
        target_map: str = "",
        need_item: str = "",
        need_quantity: int = 1,
        times: Optional[int] = None,
        report_to_master: bool = False,
        helper_location_keyword: str = "",
        helper_shop_name: str = "",
        helper_raw_text: str = "",
        source: Optional[Dict] = None,
    ) -> None:
        self.family = family
        self.task_kind = task_kind
        self.task_type = task_type
        self.raw_text = raw_text
        self.objective_text = objective_text
        self.target_npc = target_npc
        self.target_map = target_map
        self.need_item = need_item
        self.need_quantity = need_quantity
        self.times = times
        self.report_to_master = report_to_master
        self.helper_location_keyword = helper_location_keyword
        self.helper_shop_name = helper_shop_name
        self.helper_raw_text = helper_raw_text
        self.source = source or {}

    def purchase_keywords(self) -> List[str]:
        candidates = [
            f"{self.helper_location_keyword}{self.helper_shop_name}".strip(),
            self.helper_shop_name,
            self.helper_location_keyword,
            self.target_map,
            self.target_npc,
        ]
        seen = set()
        ordered: List[str] = []
        for item in candidates:
            kw = str(item or "").strip()
            if not kw or kw in seen:
                continue
            seen.add(kw)
            ordered.append(kw)
        return ordered

    def to_dict(self) -> Dict:
        return {
            "family": self.family,
            "task_kind": self.task_kind,
            "task_type": self.task_type,
            "raw_text": self.raw_text,
            "objective_text": self.objective_text,
            "target_npc": self.target_npc,
            "target_map": self.target_map,
            "need_item": self.need_item,
            "need_quantity": self.need_quantity,
            "times": self.times,
            "report_to_master": self.report_to_master,
            "helper_location_keyword": self.helper_location_keyword,
            "helper_shop_name": self.helper_shop_name,
            "helper_raw_text": self.helper_raw_text,
            "source": self.source,
        }


class AndroidShimenBot:
    def __init__(self, bot: Optional[AndroidMhxyBot] = None) -> None:
        self.bot = bot or AndroidMhxyBot()
        self.tpl_shimen_task = os.getenv("ANDROID_TPL_SHIMEN_TASK", "assets/android/memu/shimenrenwu.jpg").strip() or "assets/android/memu/shimenrenwu.jpg"
        self.tpl_confirm = os.getenv("ANDROID_TPL_CONFIRM", "assets/android/keyboard/confirm.png").strip() or "assets/android/keyboard/confirm.png"
        self.tpl_attack = os.getenv("ANDROID_TPL_ATTACK", "assets/android/memu/attack.jpg").strip() or "assets/android/memu/attack.jpg"
        self.tpl_close = os.getenv("ANDROID_TPL_CLOSE", "assets/android/memu/close.jpg").strip() or "assets/android/memu/close.jpg"
        self.tpl_transfer = os.getenv("ANDROID_TPL_TRANSFER", "assets/android/system/transfer.jpg").strip() or "assets/android/system/transfer.jpg"
        self.tpl_xianling_shop = os.getenv("ANDROID_TPL_XIANLING_SHOP", "assets/android/jineng/xianlingdianpu.jpg").strip() or "assets/android/jineng/xianlingdianpu.jpg"
        self.tpl_back_shimen = os.getenv("ANDROID_TPL_BACK_SHIMEN", "assets/android/jineng/fanhuishimen.jpg").strip() or "assets/android/jineng/fanhuishimen.jpg"
        self.tpl_task_hint_close_x = os.getenv("ANDROID_TPL_TASK_HINT_CLOSE_X", "assets/android/task/task_hint_close_x.png").strip() or "assets/android/task/task_hint_close_x.png"
        self.tpl_task_hint_ignore_btn = os.getenv("ANDROID_TPL_TASK_HINT_IGNORE_BTN", "assets/android/task/task_hint_ignore_btn.png").strip() or "assets/android/task/task_hint_ignore_btn.png"
        self.tpl_task_button = os.getenv("ANDROID_TPL_TASK_BUTTON", "assets/android/task/task_button.png").strip() or "assets/android/task/task_button.png"
        self.tpl_helper_close_x = os.getenv("ANDROID_TPL_HELPER_CLOSE_X", "assets/android/task/helper_close_x.png").strip() or "assets/android/task/helper_close_x.png"
        self.tpl_popup_close_x = os.getenv("ANDROID_TPL_POPUP_CLOSE_X", "assets/android/system/popup_close_x.png").strip() or "assets/android/system/popup_close_x.png"

        self.thr_shimen_task = float(os.getenv("ANDROID_THR_SHIMEN_TASK", "0.6") or "0.6")
        self.thr_confirm = float(os.getenv("ANDROID_THR_CONFIRM", "0.7") or "0.7")
        self.thr_attack = float(os.getenv("ANDROID_THR_ATTACK", "0.75") or "0.75")
        self.thr_close = float(os.getenv("ANDROID_THR_CLOSE", "0.75") or "0.75")
        self.thr_xianling_shop = float(os.getenv("ANDROID_THR_XIANLING_SHOP", "0.72") or "0.72")
        self.thr_back_shimen = float(os.getenv("ANDROID_THR_BACK_SHIMEN", "0.72") or "0.72")
        self.thr_task_hint_close_x = float(os.getenv("ANDROID_THR_TASK_HINT_CLOSE_X", "0.60") or "0.60")
        self.thr_task_hint_ignore_btn = float(os.getenv("ANDROID_THR_TASK_HINT_IGNORE_BTN", "0.62") or "0.62")
        self.thr_task_button = float(os.getenv("ANDROID_THR_TASK_BUTTON", "0.62") or "0.62")
        self.thr_helper_close_x = float(os.getenv("ANDROID_THR_HELPER_CLOSE_X", "0.70") or "0.70")
        self.thr_popup_close_x = float(os.getenv("ANDROID_THR_POPUP_CLOSE_X", "0.70") or "0.70")
        self.use_vl = (os.getenv("ANDROID_SHIMEN_USE_VL", "0").strip() or "0").lower() in ("1", "true", "yes")
        self.master_name = os.getenv("ANDROID_SHIMEN_MASTER_NAME", "程咬金").strip() or "程咬金"
        self.task_text = os.getenv("ANDROID_SHIMEN_TASK_TEXT", "师门任务").strip() or "师门任务"

        self.panel_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_PANEL_ROI_RATIO", "").strip()) or (0.78, 0.04, 0.995, 0.44)
        self.obj_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_OBJ_ROI_RATIO", "").strip()) or (0.78, 0.12, 0.995, 0.34)
        self.shop_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_SHOP_ROI_RATIO", "").strip()) or (0.32, 0.18, 0.94, 0.88)
        self.dialogue_tap_ratio = os.getenv("ANDROID_SHIMEN_DIALOGUE_TAP_RATIO", "0.68,0.62").strip() or "0.68,0.62"
        self.overlay_close_ratio = os.getenv("ANDROID_SHIMEN_OVERLAY_CLOSE_RATIO", "0.82,0.065").strip() or "0.82,0.065"
        self.overlay_title_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_OVERLAY_TITLE_ROI_RATIO", "").strip()) or (0.20, 0.02, 0.80, 0.16)
        self.overlay_title_keywords = [x.strip() for x in (os.getenv("ANDROID_SHIMEN_OVERLAY_TITLES", "技能学习,背包,摆摊,任务,系统").strip() or "技能学习,背包,摆摊,任务,系统").split(",") if x.strip()]
        self.transfer_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_TRANSFER_ROI_RATIO", "").strip()) or (0.84, 0.45, 0.99, 0.86)
        self.task_hint_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_TASK_HINT_ROI_RATIO", "").strip()) or (0.16, 0.10, 0.86, 0.90)
        self.task_hint_ignore_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_TASK_HINT_IGNORE_ROI_RATIO", "").strip()) or (0.55, 0.84, 0.92, 0.98)
        self.task_hint_close_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_TASK_HINT_CLOSE_ROI_RATIO", "").strip()) or (0.70, 0.00, 0.92, 0.16)
        self.task_button_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_TASK_BUTTON_ROI_RATIO", "").strip()) or (0.80, 0.14, 0.995, 0.30)
        self.shimen_times_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_TIMES_ROI_RATIO", "").strip()) or (0.84, 0.08, 0.995, 0.28)
        self.npc_option_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_NPC_OPTION_ROI_RATIO", "").strip()) or (0.74, 0.26, 0.98, 0.78)
        self.give_button_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_GIVE_BUTTON_ROI_RATIO", "").strip()) or (0.52, 0.76, 0.66, 0.86)
        self.give_title_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_GIVE_TITLE_ROI_RATIO", "").strip()) or (0.30, 0.04, 0.76, 0.18)
        self.master_menu_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_MASTER_MENU_ROI_RATIO", "").strip()) or (0.56, 0.18, 0.96, 0.75)
        self.route_choice_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_ROUTE_CHOICE_ROI_RATIO", "").strip()) or (0.74, 0.18, 0.95, 0.58)
        self.helper_close_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_HELPER_CLOSE_ROI_RATIO", "").strip()) or (0.90, 0.00, 0.995, 0.12)
        self.helper_panel_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_HELPER_PANEL_ROI_RATIO", "").strip()) or (0.64, 0.08, 0.995, 0.96)
        self.center_popup_roi_ratio = _parse_ratio_roi(os.getenv("ANDROID_SHIMEN_CENTER_POPUP_ROI_RATIO", "").strip()) or (0.18, 0.05, 0.82, 0.88)
        self.center_popup_close_ratio = os.getenv("ANDROID_SHIMEN_CENTER_POPUP_CLOSE_RATIO", "0.76,0.09").strip() or "0.76,0.09"

        self._tpl_shimen_title = self._load_shimen_title_template(self.tpl_shimen_task)
        self._tpl_confirm = self._load_template(self.tpl_confirm)
        self._tpl_attack = self._load_template(self.tpl_attack)
        self._tpl_close = self._load_template(self.tpl_close)
        self._tpl_transfer = self._load_template(self.tpl_transfer)
        self._tpl_xianling_shop = self._load_template(self.tpl_xianling_shop)
        self._tpl_back_shimen = self._load_template(self.tpl_back_shimen)
        self._tpl_task_hint_close_x = self._load_template(self.tpl_task_hint_close_x)
        self._tpl_task_hint_ignore_btn = self._load_template(self.tpl_task_hint_ignore_btn)
        self._tpl_task_button = self._load_template(self.tpl_task_button)
        self._tpl_helper_close_x = self._load_template(self.tpl_helper_close_x)
        self._tpl_popup_close_x = self._load_template(self.tpl_popup_close_x)
        self.seed_screen = os.getenv("ANDROID_SHIMEN_SEED_SCREEN", "").strip()
        self._tpl_talk = None
        if self.seed_screen and os.path.isfile(self.seed_screen):
            try:
                self._tpl_talk = self._load_seed_crop(self.seed_screen, (1760, 760, 2040, 900))
            except Exception:
                self._tpl_talk = None

    def _load_template(self, path: str) -> np.ndarray:
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"模板读取失败: {path}")
        return img

    def _load_seed_crop(self, path: str, roi: Tuple[int, int, int, int]) -> np.ndarray:
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"seed 截图读取失败: {path}")
        x1, y1, x2, y2 = roi
        h, w = img.shape[:2]
        x1 = max(0, min(int(x1), w - 1))
        x2 = max(x1 + 1, min(int(x2), w))
        y1 = max(0, min(int(y1), h - 1))
        y2 = max(y1 + 1, min(int(y2), h))
        return img[y1:y2, x1:x2].copy()

    def _load_shimen_title_template(self, path: str) -> np.ndarray:
        img = cv2.imread(path)
        if img is None:
            raise RuntimeError(f"模板读取失败: {path}")
        h, w = img.shape[:2]
        x2 = max(1, int(w * 0.55))
        y2 = max(1, int(h * 0.35))
        cropped = img[0:y2, 0:x2].copy()
        return cropped

    def _match_best(self, source_bgr: np.ndarray, template_bgr: np.ndarray) -> Tuple[Tuple[int, int], float]:
        sh, sw = source_bgr.shape[:2]
        th, tw = template_bgr.shape[:2]
        if sh < th or sw < tw:
            return ((0, 0), 0.0)
        result = cv2.matchTemplate(source_bgr, template_bgr, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        return (max_loc, float(max_val))

    def _tap_center_from_top_left(self, top_left: Tuple[int, int], template_bgr: np.ndarray, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        h, w = template_bgr.shape[:2]
        cx = int(top_left[0] + w / 2 + extra_offset[0])
        cy = int(top_left[1] + h / 2 + extra_offset[1])
        self.bot.adb.tap(cx, cy)
        time.sleep(self.bot.step_sleep_s)
        return cx, cy

    def _try_tap_template(self, template_bgr: np.ndarray, threshold: float, sleep_after: Optional[float] = None) -> Optional[Dict]:
        img = self.bot.screenshot_bgr()
        (top_left, conf) = self._match_best(img, template_bgr)
        if conf < float(threshold):
            return None
        pt = self._tap_center_from_top_left(top_left, template_bgr)
        if sleep_after is not None:
            time.sleep(float(sleep_after))
        return {"top_left": top_left, "confidence": float(conf), "tap": pt}

    def _try_tap_template_in_roi(self, template_bgr: np.ndarray, threshold: float, roi: Tuple[int, int, int, int], sleep_after: Optional[float] = None) -> Optional[Dict]:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = roi
        cropped = img[y1:y2, x1:x2]
        (top_left, conf) = self._match_best(cropped, template_bgr)
        if conf < float(threshold):
            return None
        abs_top_left = (int(top_left[0] + x1), int(top_left[1] + y1))
        pt = self._tap_center_from_top_left(abs_top_left, template_bgr)
        if sleep_after is not None:
            time.sleep(float(sleep_after))
        return {"top_left": abs_top_left, "confidence": float(conf), "tap": pt}

    def _task_panel_fingerprint(self) -> np.ndarray:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = _roi_from_ratio(img, self.panel_roi_ratio)
        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
        return small

    def _task_panel_visible(self) -> bool:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = _roi_from_ratio(img, self.panel_roi_ratio)
        cropped = img[y1:y2, x1:x2].copy()
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        if self.task_text and self.task_text in text:
            return True
        (top_left, conf) = self._match_best(img, self._tpl_shimen_title)
        if conf >= max(0.50, float(self.thr_shimen_task) - 0.08):
            return True
        return ("师门" in text) or ("任务" in text)

    def _objective_roi(self, img_bgr: np.ndarray) -> Tuple[int, int, int, int]:
        return _roi_from_ratio(img_bgr, self.obj_roi_ratio)

    def _objective_text(self) -> str:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = self._objective_roi(img)
        cropped = img[y1:y2, x1:x2].copy()
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        if text:
            return text
        panel = self._task_panel_structured()
        return str((panel or {}).get("raw_text") or "").strip()

    def _objective_structured(self) -> Optional[Dict]:
        if not self.use_vl:
            return None
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = self._objective_roi(img)
        cropped = img[y1:y2, x1:x2].copy()
        schema = {
            "type": "object",
            "properties": {
                "task_type": {"type": "string"},
                "need_item": {"type": "string"},
                "need_quantity": {"type": "integer"},
                "target_npc": {"type": "string"},
                "target_map": {"type": "string"},
            },
        }
        prompt = (
            "从图片中提取师门任务目标信息。\n"
            "task_type 只允许：talk, deliver_item, buy_item, patrol, battle, submit, unknown。\n"
            "need_item/need_quantity 仅在需要物品时填写，否则留空或 0。\n"
            "target_npc/target_map 若能识别就填写。"
        )
        try:
            r = siliflow_client.siliconflow_qwen_structured(cropped, prompt=prompt, schema=schema)
        except Exception:
            return None
        parsed = r.get("parsed")
        return parsed if isinstance(parsed, dict) else None

    def ensure_ui_visible(self) -> bool:
        if self._task_panel_visible():
            return True
        img = self.bot.screenshot_bgr()
        h, w = img.shape[:2]
        if self.use_vl:
            import vl_locator

            roi = (int(w * 0.70), 0, w, int(h * 0.25))
            located = None
            for txt in ("任务", "师门任务"):
                try:
                    located = vl_locator.locate_text_center(img, txt, roi=roi)
                except Exception:
                    located = None
                if located is not None:
                    break
            if located is not None:
                self.bot.adb.tap(int(located["x"]), int(located["y"]))
                time.sleep(0.8)
                return self._task_panel_visible()
        self.bot.adb.tap(int(w * 0.94), int(h * 0.12))
        time.sleep(0.8)
        return self._task_panel_visible()

    def _task_panel_changed(self, before: np.ndarray, diff_threshold: float = 10.0) -> bool:
        after = self._task_panel_fingerprint()
        diff = cv2.absdiff(before, after)
        score = float(diff.mean())
        return score >= float(diff_threshold)

    def _objective_fingerprint(self) -> np.ndarray:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = self._objective_roi(img)
        roi = img[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (96, 64), interpolation=cv2.INTER_AREA)
        return small

    def _objective_changed(self, before: np.ndarray, diff_threshold: float = 8.0) -> bool:
        after = self._objective_fingerprint()
        diff = cv2.absdiff(before, after)
        score = float(diff.mean())
        return score >= float(diff_threshold)

    def talk_to_master_and_progress(self, max_steps: int = 25) -> Dict:
        img = self.bot.screenshot_bgr()
        h, w = img.shape[:2]
        before = self._objective_fingerprint()
        if self._tpl_talk is not None:
            (tl, conf) = self._match_best(img, self._tpl_talk)
            if conf >= 0.62:
                self._tap_center_from_top_left(tl, self._tpl_talk)
            else:
                self.bot.adb.tap(int(w * 0.35), int(h * 0.25))
        else:
            self.bot.adb.tap(int(w * 0.35), int(h * 0.25))
        time.sleep(0.8)
        actions = []
        for _ in range(max(1, int(max_steps))):
            common = self._handle_common_once()
            if common is not None:
                actions.append(common)
                if self._objective_changed(before, diff_threshold=float(os.getenv("ANDROID_SHIMEN_OBJ_DIFF_THR", "10") or "10")):
                    return {"ok": True, "actions": actions, "changed": True}
                continue
            x, y = self._tap_dialogue_area()
            actions.append({"action": "tap_dialogue", "tap": (x, y)})
            if self._objective_changed(before, diff_threshold=float(os.getenv("ANDROID_SHIMEN_OBJ_DIFF_THR", "10") or "10")):
                stable = 0
                for _ in range(3):
                    time.sleep(0.7)
                    if self._objective_changed(before, diff_threshold=float(os.getenv("ANDROID_SHIMEN_OBJ_DIFF_THR", "10") or "10")):
                        stable += 1
                return {"ok": stable >= 2, "actions": actions, "changed": stable >= 2}
        return {"ok": False, "actions": actions, "changed": False}

    def _tap_dialogue_area(self) -> Tuple[int, int]:
        img = self.bot.screenshot_bgr()
        h, w = img.shape[:2]
        parts = [p.strip() for p in self.dialogue_tap_ratio.split(",") if p.strip()]
        rx = float(parts[0]) if len(parts) >= 1 else 0.68
        ry = float(parts[1]) if len(parts) >= 2 else 0.62
        x = int(w * rx)
        y = int(h * ry)
        self.bot.adb.tap(x, y)
        time.sleep(self.bot.step_sleep_s)
        return x, y

    def _maybe_close_overlay(self, img_bgr: np.ndarray) -> Optional[Dict]:
        try:
            x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.overlay_title_roi_ratio)
            cropped = img_bgr[y1:y2, x1:x2].copy()
            r = siliflow_client.siliconflow_paddleocr(cropped)
            title = str(r.get("content") or "").strip()
        except Exception:
            title = ""
        if not title:
            return None
        hit = None
        for kw in self.overlay_title_keywords:
            if kw and kw in title:
                hit = kw
                break
        if not hit:
            return None
        h, w = img_bgr.shape[:2]
        parts = [p.strip() for p in self.overlay_close_ratio.split(",") if p.strip()]
        rx = float(parts[0]) if len(parts) >= 1 else 0.80
        ry = float(parts[1]) if len(parts) >= 2 else 0.095
        x = int(w * rx)
        y = int(h * ry)
        self.bot.adb.tap(x, y)
        time.sleep(self.bot.step_sleep_s)
        return {"action": "close_overlay", "title": title, "hit": hit, "tap": (x, y), "title_roi": [x1, y1, x2, y2]}

    def _overlay_likely_present(self, img_bgr: np.ndarray) -> bool:
        h, w = img_bgr.shape[:2]
        x1 = int(w * 0.18)
        x2 = int(w * 0.82)
        y1 = int(h * 0.16)
        y2 = int(h * 0.84)
        if x2 <= x1 or y2 <= y1:
            return False
        roi = img_bgr[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        m = float(gray.mean())
        s = float(gray.std())
        return (m >= 105.0) and (s <= 90.0)

    def _tap_overlay_close_fallback(self, img_bgr: np.ndarray) -> Optional[Dict]:
        if not self._overlay_likely_present(img_bgr):
            return None
        roi_close_x = _roi_from_ratio(img_bgr, self.task_hint_close_roi_ratio)
        r = self._try_tap_template_in_roi(self._tpl_task_hint_close_x, threshold=self.thr_task_hint_close_x, roi=roi_close_x, sleep_after=0.4)
        if r is not None:
            return {"action": "close_overlay_tpl", **r}
        h, w = img_bgr.shape[:2]
        taps = []
        parts = [p.strip() for p in self.overlay_close_ratio.split(",") if p.strip()]
        base_rx = float(parts[0]) if len(parts) >= 1 else 0.82
        base_ry = float(parts[1]) if len(parts) >= 2 else 0.065
        candidates = [
            (base_rx, base_ry),
            (0.85, 0.065),
            (0.88, 0.065),
            (0.90, 0.065),
            (0.82, 0.095),
            (0.85, 0.095),
        ]
        for rx, ry in candidates:
            x = int(w * rx)
            y = int(h * ry)
            self.bot.adb.tap(x, y)
            taps.append((x, y))
            time.sleep(max(0.05, self.bot.step_sleep_s * 0.5))
        return {"action": "close_overlay_fallback", "taps": taps}

    def _task_hint_panel_likely(self, img_bgr: np.ndarray) -> bool:
        h, w = img_bgr.shape[:2]
        x1 = int(w * 0.40)
        x2 = int(w * 0.60)
        y1 = int(h * 0.86)
        y2 = int(h * 0.97)
        if x2 <= x1 or y2 <= y1:
            return False
        roi = img_bgr[y1:y2, x1:x2]
        b, g, r = [float(x) for x in roi.mean(axis=(0, 1))]
        return (r >= 130.0) and (g <= 110.0) and (b <= 110.0)

    def _try_tap_text(self, texts, roi: Optional[Tuple[int, int, int, int]] = None, sleep_after: Optional[float] = None) -> Optional[Dict]:
        if not self.use_vl:
            return None
        import vl_locator

        img = self.bot.screenshot_bgr()
        for txt in texts:
            try:
                located = vl_locator.locate_text_center(img, str(txt), roi=roi)
            except Exception:
                located = None
            if located is None:
                continue
            x = int(located["x"])
            y = int(located["y"])
            self.bot.adb.tap(x, y)
            time.sleep(self.bot.step_sleep_s if sleep_after is None else float(sleep_after))
            return {"text": str(txt), "tap": (x, y), "located": located}
        return None

    def _task_panel_structured(self) -> Optional[Dict]:
        if not self.use_vl:
            return None
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = _roi_from_ratio(img, self.panel_roi_ratio)
        cropped = img[y1:y2, x1:x2].copy()
        schema = {
            "type": "object",
            "properties": {
                "task_kind": {"type": "string"},
                "target_npc": {"type": "string"},
                "need_item": {"type": "string"},
                "need_quantity": {"type": "integer"},
                "times": {"type": "integer"},
                "raw_text": {"type": "string"},
            },
        }
        prompt = (
            "从这张梦幻西游师门任务追踪截图里提取当前任务信息。"
            "task_kind 只允许: deliver_npc, buy_item, patrol, battle, report_master, talk, unknown。"
            "如果是送信/送东西给NPC，task_kind=deliver_npc。"
            "如果是向师父复命/报告，task_kind=report_master。"
            "times 填写“当前第X次”的 X。"
            "raw_text 原样概括任务栏内容。"
        )
        try:
            r = siliflow_client.siliconflow_qwen_structured(cropped, prompt=prompt, schema=schema)
        except Exception:
            return None
        parsed = r.get("parsed")
        if not isinstance(parsed, dict):
            return None
        parsed["roi"] = [x1, y1, x2, y2]
        return parsed

    def _dialogue_panel_likely(self, img_bgr: np.ndarray) -> bool:
        if self._give_panel_likely(img_bgr):
            return False
        h, w = img_bgr.shape[:2]
        x1 = int(w * 0.04)
        x2 = int(w * 0.98)
        y1 = int(h * 0.77)
        y2 = int(h * 0.98)
        if x2 <= x1 or y2 <= y1:
            return False
        roi = img_bgr[y1:y2, x1:x2]
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        return float(gray.mean()) <= 120.0

    def _tap_npc_option(self, option_index: int = 1, sleep_after: float = 1.0) -> Dict:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = _roi_from_ratio(img, self.npc_option_roi_ratio)
        width = max(1, x2 - x1)
        height = max(3, y2 - y1)
        idx = max(1, min(int(option_index), 3))
        slot_h = height / 3.0
        x = int(x1 + width * 0.58)
        y = int(y1 + slot_h * (idx - 0.5))
        self.bot.adb.tap(x, y)
        time.sleep(float(sleep_after))
        return {"tap": (x, y), "option_index": idx, "roi": [x1, y1, x2, y2]}

    def _tap_master_menu_option(self, row: int, col: int = 1, sleep_after: float = 1.0) -> Dict:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = _roi_from_ratio(img, self.master_menu_roi_ratio)
        width = max(2, x2 - x1)
        height = max(2, y2 - y1)
        row_idx = max(1, min(int(row), 4))
        col_idx = 1 if int(col) <= 1 else 2
        cell_w = width / 2.0
        cell_h = height / 4.0
        x = int(x1 + cell_w * (col_idx - 0.5))
        y = int(y1 + cell_h * (row_idx - 0.5))
        self.bot.adb.tap(x, y)
        time.sleep(float(sleep_after))
        return {"tap": (x, y), "row": row_idx, "col": col_idx, "roi": [x1, y1, x2, y2]}

    def _try_handle_npc_dialog_once(self, img_bgr: np.ndarray) -> Optional[Dict]:
        if not self._dialogue_panel_likely(img_bgr):
            return None
        panel = self._task_panel_structured() or {}
        raw_text = str(panel.get("raw_text") or "").strip()
        task_kind = str(panel.get("task_kind") or "").strip().lower()
        target_npc = str(panel.get("target_npc") or "").strip()
        if task_kind == "report_master" or ("师父" in raw_text) or (target_npc == "师父"):
            r = self._try_tap_text(["任务"], roi=_roi_from_ratio(img_bgr, self.master_menu_roi_ratio), sleep_after=1.0)
            if r is not None:
                return {"action": "master_task_text", **r}
            tapped = self._tap_master_menu_option(row=2, col=1, sleep_after=1.0)
            return {"action": "master_task_grid", **tapped}
        roi = _roi_from_ratio(img_bgr, self.npc_option_roi_ratio)
        r = self._try_tap_text(["师门任务"], roi=roi, sleep_after=1.0)
        if r is not None:
            return {"action": "npc_option_shimen_text", **r}
        tapped = self._tap_npc_option(option_index=1, sleep_after=1.0)
        return {"action": "npc_option_1", **tapped}

    def _give_panel_likely(self, img_bgr: np.ndarray) -> bool:
        x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.give_title_roi_ratio)
        if x2 <= x1 or y2 <= y1:
            return False
        cropped = img_bgr[y1:y2, x1:x2].copy()
        text = ""
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        roi_btn = _roi_from_ratio(img_bgr, self.give_button_roi_ratio)
        bx1, by1, bx2, by2 = roi_btn
        red_likely = False
        if bx2 > bx1 and by2 > by1:
            btn = img_bgr[by1:by2, bx1:bx2]
            b, g, r = [float(v) for v in btn.mean(axis=(0, 1))]
            red_likely = (r >= 110.0) and (r > g + 15.0) and (r > b + 15.0)
        return ("给予" in text) or ("道具" in text) or ("任务" in text) or red_likely

    def _route_choice_panel_likely(self, img_bgr: np.ndarray) -> bool:
        x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.route_choice_roi_ratio)
        cropped = img_bgr[y1:y2, x1:x2].copy()
        text = ""
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        return ("请选择" in text) or ("寻路目标" in text)

    def _helper_panel_likely(self, img_bgr: np.ndarray) -> bool:
        x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.helper_close_roi_ratio)
        cropped = img_bgr[y1:y2, x1:x2].copy()
        try:
            (top_left, conf) = self._match_best(cropped, self._tpl_helper_close_x)
        except Exception:
            return False
        return conf >= float(self.thr_helper_close_x)

    def _close_helper_panel_once(self, img_bgr: np.ndarray) -> Optional[Dict]:
        roi = _roi_from_ratio(img_bgr, self.helper_close_roi_ratio)
        r = self._try_tap_template_in_roi(self._tpl_helper_close_x, threshold=self.thr_helper_close_x, roi=roi, sleep_after=0.8)
        if r is not None:
            return {"action": "close_helper_panel", **r}
        return None

    def _center_popup_likely(self, img_bgr: np.ndarray) -> bool:
        """
        识别居中的无关弹窗，例如小地图/场景详情窗。
        这类弹窗通常位于画面中央，右侧带“前往/筛选/世界”等按钮，会阻断任务点击。
        """
        x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.center_popup_roi_ratio)
        cropped = img_bgr[y1:y2, x1:x2].copy()
        text = ""
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        hits = 0
        for kw in ("前往", "筛选", "世界", "X:", "Y:"):
            if kw in text:
                hits += 1
        if hits >= 2:
            return True
        # 视觉特征兜底：中央大块浅色边框/面板
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        bright_ratio = float((gray >= 175).mean())
        return bright_ratio >= 0.12

    def _find_center_popup_bounds(self, img_bgr: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.center_popup_roi_ratio)
        cropped = img_bgr[y1:y2, x1:x2].copy()
        gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
        mask = (gray >= 180).astype(np.uint8) * 255
        num, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        best = None
        for i in range(1, num):
            sx, sy, sw, sh, area = stats[i]
            if area < 20000:
                continue
            if sw < 500 or sh < 250:
                continue
            if best is None or area > best[4]:
                best = (sx, sy, sw, sh, area)
        if best is None:
            return None
        sx, sy, sw, sh, _ = best
        return (x1 + sx, y1 + sy, x1 + sx + sw, y1 + sy + sh)

    def _close_center_popup_once(self, img_bgr: np.ndarray) -> Optional[Dict]:
        if not self._center_popup_likely(img_bgr):
            return None
        bounds = self._find_center_popup_bounds(img_bgr)
        roi_tpl = None
        if bounds is not None:
            bx1, by1, bx2, by2 = bounds
            roi_tpl = (
                max(0, int(bx2 - 180)),
                max(0, int(by1 - 60)),
                min(img_bgr.shape[1], int(bx2 + 80)),
                min(img_bgr.shape[0], int(by1 + 140)),
            )
            r = self._try_tap_template_in_roi(self._tpl_popup_close_x, threshold=self.thr_popup_close_x, roi=roi_tpl, sleep_after=0.3)
            if r is not None:
                return {"action": "close_center_popup_tpl", **r, "bounds": [int(v) for v in bounds], "roi": [int(v) for v in roi_tpl]}
            base_x = int(bx2 - max(22, (bx2 - bx1) * 0.04))
            base_y = int(by1 + max(22, (by2 - by1) * 0.04))
        else:
            h, w = img_bgr.shape[:2]
            parts = [p.strip() for p in self.center_popup_close_ratio.split(",") if p.strip()]
            rx = float(parts[0]) if len(parts) >= 1 else 0.76
            ry = float(parts[1]) if len(parts) >= 2 else 0.09
            base_x = int(w * rx)
            base_y = int(h * ry)
        taps = [
            (base_x, base_y),
            (base_x - 10, base_y),
            (base_x + 10, base_y),
            (base_x, base_y + 8),
        ]
        for x, y in taps:
            self.bot.adb.tap(x, y)
            time.sleep(max(0.08, self.bot.step_sleep_s * 0.5))
        return {
            "action": "close_center_popup",
            "taps": [(int(x), int(y)) for x, y in taps],
            "bounds": [int(v) for v in bounds] if bounds is not None else None,
        }

    def cleanup_startup_popups(self, max_steps: int = 6) -> Dict:
        actions = []
        for _ in range(max(1, int(max_steps))):
            img = self.bot.screenshot_bgr()
            acted = self._close_center_popup_once(img)
            if acted is None:
                acted = self._close_helper_panel_once(img) if self._helper_panel_likely(img) else None
            if acted is None:
                acted = self._tap_overlay_close_fallback(img)
            if acted is None:
                break
            actions.append(acted)
            time.sleep(0.4)
        return {"ok": True, "actions": actions}

    def _read_helper_panel_structured(self, img_bgr: np.ndarray) -> Optional[Dict]:
        """
        读取右侧“精灵问答/帮助”面板内容，抽取买物/地点信息。
        这里不做任务枚举，只返回可用于“地图搜索/寻路”的关键词。
        """
        x1, y1, x2, y2 = _roi_from_ratio(img_bgr, self.helper_panel_roi_ratio)
        cropped = img_bgr[y1:y2, x1:x2].copy()
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        schema = {
            "type": "object",
            "properties": {
                "location_keyword": {"type": "string"},
                "shop_name": {"type": "string"},
                "item_name": {"type": "string"},
                "raw_text": {"type": "string"},
            },
        }
        # 仅在启用 VL 时做结构化抽取；否则退化为 PaddleOCR 的原文。
        parsed = None
        if self.use_vl:
            try:
                prompt = (
                    "从这张梦幻西游帮助面板截图中提取和当前师门买物/寻物任务有关的地点信息。"
                    "location_keyword 填一个最适合地图搜索的地点或NPC关键词（例如 长安/大唐国境/杂货店）。"
                    "shop_name 填店铺名（例如 杂货店/药店/兵器铺）。"
                    "item_name 填物品名（如果能看出）。"
                    "raw_text 概括主要内容。"
                )
                rr = siliflow_client.siliconflow_qwen_structured(cropped, prompt=prompt, schema=schema)
                if isinstance(rr.get("parsed"), dict):
                    parsed = rr.get("parsed")
            except Exception:
                parsed = None
        out = {
            "roi": [x1, y1, x2, y2],
            "raw_ocr": text,
        }
        if isinstance(parsed, dict):
            out.update(parsed)
        else:
            out["raw_text"] = text
        return out

    def _build_task_context(self) -> ShimenTaskContext:
        # 任务栏（追踪）为主来源
        panel = self._task_panel_structured() or {}
        objective_text = ""
        try:
            objective_text = self._objective_text()
        except Exception:
            objective_text = ""
        times = None
        try:
            times = self.detect_shimen_times().get("times")
        except Exception:
            times = None

        raw_text = str(panel.get("raw_text") or "").strip()
        task_kind = str(panel.get("task_kind") or "").strip().lower()
        need_item = str(panel.get("need_item") or "").strip()
        need_qty = panel.get("need_quantity")
        need_qty_int = int(need_qty) if isinstance(need_qty, int) and need_qty > 0 else 1
        if not need_item:
            merged_text = "\n".join([raw_text, str(objective_text or "").strip()])
            patterns = [
                r"(?:买到|买个|购买|找到|寻来|寻得|弄来)\s*([^\s，。；、\n]{1,12}?)(?:送给|交给|给予|给师父|回来|当做)",
                r"(?:需要|上交|提交)\s*([^\s，。；、\n]{1,12}?)(?:[xX×*]\s*\d+|一份|一个|一把|一只|一件|$)",
            ]
            for pattern in patterns:
                m = re.search(pattern, merged_text)
                if not m:
                    continue
                candidate = str(m.group(1) or "").strip()
                candidate = re.sub(r"^(一个|一把|一只|一件|一株|一朵|一瓶|一份)", "", candidate)
                if candidate:
                    need_item = candidate
                    break

        report_to_master = False
        if task_kind == "report_master":
            report_to_master = True
        if ("报告" in raw_text) and (("师父" in raw_text) or ("师门" in raw_text)):
            report_to_master = True
        if ("报告" in objective_text) and (("师父" in objective_text) or ("师门" in objective_text)):
            report_to_master = True

        combined_text = " ".join([raw_text, str(objective_text or "").strip(), str(need_item or "").strip()]).strip()
        buy_like = False
        if need_item:
            buy_like = True
        if ("买到" in combined_text) or ("找到" in combined_text) or ("寻物" in combined_text):
            buy_like = True

        family = "unknown"
        if report_to_master:
            family = "report"
        elif buy_like:
            family = "buy_item"
        elif task_kind == "deliver_npc":
            family = "deliver"
        elif task_kind in ("battle", "patrol"):
            family = "battle"

        return ShimenTaskContext(
            family=family,
            task_kind=task_kind,
            raw_text=raw_text,
            objective_text=str(objective_text or "").strip(),
            target_npc=str(panel.get("target_npc") or "").strip(),
            target_map=str(panel.get("target_map") or "").strip(),
            need_item=need_item,
            need_quantity=need_qty_int,
            times=times,
            report_to_master=report_to_master,
            source={"panel": panel},
        )

    def _handle_route_choice_once(self, img_bgr: np.ndarray) -> Optional[Dict]:
        if not self._route_choice_panel_likely(img_bgr):
            return None
        panel = self._task_panel_structured() or {}
        item = str(panel.get("need_item") or "").strip()
        roi = _roi_from_ratio(img_bgr, self.route_choice_roi_ratio)
        if item:
            r = self._try_tap_text([item], roi=roi, sleep_after=1.0)
            if r is not None:
                return {"action": "route_choice_item_text", **r}
        x1, y1, x2, y2 = roi
        x = int((x1 + x2) / 2)
        y = int(y1 + (y2 - y1) * 0.68)
        self.bot.adb.tap(x, y)
        time.sleep(1.0)
        return {"action": "route_choice_item_fallback", "tap": (x, y), "roi": [x1, y1, x2, y2], "item": item}

    def _try_handle_give_panel_once(self, img_bgr: np.ndarray) -> Optional[Dict]:
        roi_btn = _roi_from_ratio(img_bgr, self.give_button_roi_ratio)
        r = self._try_tap_text(["给予"], roi=roi_btn, sleep_after=1.0)
        if r is not None:
            return {"action": "give_text", **r}
        if not self._give_panel_likely(img_bgr):
            return None
        x1, y1, x2, y2 = roi_btn
        x = int((x1 + x2) / 2)
        y = int((y1 + y2) / 2)
        self.bot.adb.tap(x, y)
        time.sleep(1.0)
        return {"action": "give_button_fallback", "tap": (x, y), "roi": [x1, y1, x2, y2]}

    def _handle_common_once(self) -> Optional[Dict]:
        img = self.bot.screenshot_bgr()
        h, w = img.shape[:2]
        r = self._close_center_popup_once(img)
        if r is not None:
            return r
        r = self._close_helper_panel_once(img) if self._helper_panel_likely(img) else None
        if r is not None:
            return r
        r = self._handle_route_choice_once(img)
        if r is not None:
            return r
        r = self._try_handle_give_panel_once(img)
        if r is not None:
            return r
        r = self._try_handle_npc_dialog_once(img)
        if r is not None:
            return r
        if self._task_hint_panel_likely(img):
            roi_ignore = _roi_from_ratio(img, self.task_hint_ignore_roi_ratio)
            r = self._try_tap_template_in_roi(self._tpl_task_hint_ignore_btn, threshold=self.thr_task_hint_ignore_btn, roi=roi_ignore, sleep_after=0.9)
            if r is not None:
                return {"action": "ignore_task_hint_tpl", **r}
            r = self._try_tap_text(["忽略任务提示", "忽略该任务", "忽略"], roi=roi_ignore, sleep_after=0.9)
            if r is not None:
                return {"action": "ignore_task_hint_text", **r}
            roi_close_x = _roi_from_ratio(img, self.task_hint_close_roi_ratio)
            r = self._try_tap_template_in_roi(self._tpl_task_hint_close_x, threshold=self.thr_task_hint_close_x, roi=roi_close_x, sleep_after=0.6)
            if r is not None:
                return {"action": "close_task_hint_tpl", **r}
            r = self._tap_overlay_close_fallback(img)
            if r is not None:
                return r
        r = self._try_tap_text(["师门寻路", "寻路"], roi=_roi_from_ratio(img, self.task_hint_roi_ratio), sleep_after=0.9)
        if r is not None:
            return {"action": "shimen_route", **r}
        r = self._maybe_close_overlay(img)
        if r is not None:
            return r
        r = self._try_tap_text(["传送"], roi=_roi_from_ratio(img, self.transfer_roi_ratio), sleep_after=0.8)
        if r is not None:
            return {"action": "transfer_text", **r}
        roi_close = (int(w * 0.72), 0, w, int(h * 0.22))
        r = self._try_tap_text(["关闭", "取消", "返回"], roi=roi_close, sleep_after=0.4)
        if r is not None:
            return {"action": "close_text", **r}
        r = self._try_tap_template_in_roi(self._tpl_close, threshold=self.thr_close, roi=roi_close)
        if r is not None:
            return {"action": "close", **r}

        roi_confirm = (int(w * 0.28), int(h * 0.72), int(w * 0.72), h)
        r = self._try_tap_text(["确定", "确认", "同意", "继续"], roi=roi_confirm, sleep_after=0.4)
        if r is not None:
            return {"action": "confirm_text", **r}
        r = self._try_tap_template_in_roi(self._tpl_confirm, threshold=self.thr_confirm, roi=roi_confirm)
        if r is not None:
            return {"action": "confirm", **r}
        roi_center = (int(w * 0.30), int(h * 0.25), int(w * 0.70), int(h * 0.85))
        r = self._try_tap_template(self._tpl_transfer, threshold=0.7)
        if r is not None:
            return {"action": "transfer", **r}

        roi_panel = _roi_from_ratio(img, self.panel_roi_ratio)
        r = self._try_tap_text(["仙灵店铺"], roi=roi_panel, sleep_after=0.8)
        if r is not None:
            return {"action": "xianling_shop_text", **r}
        r = self._try_tap_template(self._tpl_xianling_shop, threshold=self.thr_xianling_shop, sleep_after=0.8)
        if r is not None:
            return {"action": "xianling_shop", **r}
        r = self._try_tap_text(["返回师门"], roi=roi_panel, sleep_after=0.8)
        if r is not None:
            return {"action": "back_shimen_text", **r}
        r = self._try_tap_template(self._tpl_back_shimen, threshold=self.thr_back_shimen, sleep_after=0.8)
        if r is not None:
            return {"action": "back_shimen", **r}
        r = self._tap_overlay_close_fallback(img)
        if r is not None:
            return r
        return None

    def tap_shimen_task(self) -> Optional[Dict]:
        if self.use_vl:
            import vl_locator

            img = self.bot.screenshot_bgr()
            roi = _roi_from_ratio(img, self.panel_roi_ratio)
            located = None
            try:
                located = vl_locator.locate_text_center(img, self.task_text, roi=roi)
            except Exception:
                located = None
            if located is not None:
                x = int(located["x"])
                # 标题“师门任务”通常在任务栏顶部，真正的追踪点击区在其下方正文。
                # 这里向下偏移到正文区域，避免误打开任务详情/地图弹窗。
                x1, y1, x2, y2 = roi
                y = int(min(y2 - 8, located["y"] + max(55, int((y2 - y1) * 0.18))))
                self.bot.adb.tap(x, y)
                time.sleep(self.bot.step_sleep_s)
                return {"template": "vl_text", "text": self.task_text, "tap": (x, y), "located": located, "roi": [x1, y1, x2, y2]}
        img = self.bot.screenshot_bgr()
        (top_left, conf) = self._match_best(img, self._tpl_shimen_title)
        if conf < self.thr_shimen_task:
            return None
        th, tw = self._tpl_shimen_title.shape[:2]
        x = int(top_left[0] + tw * 0.68)
        y = int(top_left[1] + th + max(55, int(th * 1.2)))
        self.bot.adb.tap(x, y)
        time.sleep(self.bot.step_sleep_s)
        pt = (x, y)
        return {"template": "shimen_title", "top_left": top_left, "confidence": conf, "tap": pt}

    def wait_arrived(self) -> Dict:
        try:
            return self.bot.wait_until_arrived_by_coord()
        except Exception as e:
            time.sleep(float(os.getenv("ANDROID_FALLBACK_MOVE_WAIT_S", "8") or "8"))
            return {"arrived": False, "reason": "coord_unavailable", "error": str(e)}

    def ensure_master_reachable(self) -> Dict:
        try:
            r = self.bot.map_search_and_go(self.master_name)
        except Exception as e:
            return {"ok": False, "reason": "map_search_failed", "error": str(e), "master": self.master_name}
        time.sleep(float(os.getenv("ANDROID_SHIMEN_MASTER_MOVE_WAIT_S", "10") or "10"))
        return {"ok": True, "map": r, "master": self.master_name}

    def detect_shimen_times(self) -> Dict:
        img = self.bot.screenshot_bgr()
        x1, y1, x2, y2 = _roi_from_ratio(img, self.shimen_times_roi_ratio)
        cropped = img[y1:y2, x1:x2].copy()
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        m = re.search(r"当前第\\s*(\\d+)\\s*次", text)
        if m:
            return {"times": int(m.group(1)), "raw_text": text, "roi": [x1, y1, x2, y2]}
        nums = re.findall(r"\\d+", text)
        times = int(nums[0]) if nums else None
        if times is None:
            parsed = self._task_panel_structured() or {}
            parsed_times = parsed.get("times")
            if isinstance(parsed_times, int):
                return {"times": parsed_times, "raw_text": str(parsed.get("raw_text") or ""), "roi": parsed.get("roi") or [x1, y1, x2, y2]}
        return {"times": times, "raw_text": text, "roi": [x1, y1, x2, y2]}

    def open_task_overview_and_read_done(self) -> Dict:
        import vl_locator

        img0 = self.bot.screenshot_bgr()
        h, w = img0.shape[:2]
        opened_img = None
        roi_close = _roi_from_ratio(img0, self.task_hint_close_roi_ratio)

        candidates = [(0.92, 0.20), (0.92, 0.14), (0.94, 0.26)]
        for i in range(3):
            x = None
            y = None
            roi_btn = _roi_from_ratio(img0, self.task_button_roi_ratio)
            cropped_btn = img0[roi_btn[1] : roi_btn[3], roi_btn[0] : roi_btn[2]].copy()
            tl, conf = self._match_best(cropped_btn, self._tpl_task_button)
            if conf >= float(self.thr_task_button):
                th, tw = self._tpl_task_button.shape[:2]
                x = int(roi_btn[0] + tl[0] + tw * 0.5)
                y = int(roi_btn[1] + tl[1] + th * 0.5)
            try:
                located = vl_locator.locate_text_center(img0, "任务", roi=(int(w * 0.84), 0, w, int(h * 0.30))) if x is None else None
            except Exception:
                located = None
            if located is not None:
                x = int(located["x"])
                y = int(located["y"])
            if x is None or y is None:
                rx, ry = candidates[i % len(candidates)]
                x = int(w * rx)
                y = int(h * ry)
            self.bot.adb.tap(x, y)
            time.sleep(0.9)
            img1 = self.bot.screenshot_bgr()
            tl, conf = self._match_best(img1[roi_close[1] : roi_close[3], roi_close[0] : roi_close[2]].copy(), self._tpl_task_hint_close_x)
            if conf >= float(self.thr_task_hint_close_x):
                opened_img = img1
                break
            img0 = img1

        img = opened_img if opened_img is not None else self.bot.screenshot_bgr()
        roi_text = (int(w * 0.34), int(h * 0.14), int(w * 0.92), int(h * 0.46))
        x1, y1, x2, y2 = roi_text
        cropped = img[y1:y2, x1:x2].copy()
        try:
            r = siliflow_client.siliconflow_paddleocr(cropped)
            text = str(r.get("content") or "").strip()
        except Exception:
            text = ""
        m = re.search(r"当前已完成\\s*师门任务\\s*(\\d+)\\s*个", text)
        done = int(m.group(1)) if m else None
        roi_close_x = _roi_from_ratio(img, self.task_hint_close_roi_ratio)
        closed = self._try_tap_template_in_roi(self._tpl_task_hint_close_x, threshold=self.thr_task_hint_close_x, roi=roi_close_x, sleep_after=0.6)
        return {"done": done, "raw_text": text, "roi": [x1, y1, x2, y2], "opened": opened_img is not None, "closed": closed}

    def _compact_text(self, text: str) -> str:
        return re.sub(r"\s+", "", str(text or ""))

    def _task_advanced(self, before_ctx: Optional[ShimenTaskContext], after_ctx: Optional[ShimenTaskContext]) -> bool:
        if before_ctx is None or after_ctx is None:
            return False
        before_obj = self._compact_text(before_ctx.objective_text)
        after_obj = self._compact_text(after_ctx.objective_text)
        before_item = self._compact_text(before_ctx.need_item)
        after_item = self._compact_text(after_ctx.need_item)
        if before_item and after_item and before_item != after_item:
            return True
        if before_ctx.family and after_ctx.family and before_ctx.family != after_ctx.family and after_ctx.family != "unknown":
            return True
        if before_obj and after_obj and before_obj != after_obj:
            if before_item and before_item in before_obj and before_item not in after_obj:
                return True
            if before_ctx.family == "buy_item" and "买到" in before_obj and "买到" not in after_obj:
                return True
            if len(after_obj) >= 4:
                return True
        return False

    def _submit_to_master_until_reward(
        self,
        before_times: Optional[int],
        max_wait_s: float = 90.0,
        prefer_direct_master: bool = False,
        before_ctx: Optional[ShimenTaskContext] = None,
    ) -> Dict:
        deadline = time.time() + max(5.0, float(max_wait_s))
        actions = []
        while time.time() < deadline:
            common = self._handle_common_once()
            if common is not None:
                actions.append(common)
                if prefer_direct_master and str(common.get("action") or "") in (
                    "npc_option_1",
                    "npc_option_shimen_text",
                    "master_task_grid",
                    "master_task_text",
                    "tap_dialogue",
                ):
                    # 买物复命阶段优先直达师父，避免被对话菜单循环吞掉提交流程。
                    pass
                else:
                    time.sleep(0.2)
                    continue
                time.sleep(0.2)
            tapped = None
            if not prefer_direct_master:
                tapped = self.tap_shimen_task()
                actions.append({"action": "tap_task_to_master", "tap_task": tapped})
            if prefer_direct_master or tapped is None:
                nav = self.ensure_master_reachable()
                actions.append({"action": "nav_master", "nav": nav})
            _ = self.wait_arrived()
            talk = self.talk_to_master_and_progress(max_steps=int(os.getenv("ANDROID_SHIMEN_MASTER_STEPS", "25") or "25"))
            actions.append({"action": "talk_master", "talk": talk})
            now = self.detect_shimen_times()
            after_times = now.get("times")
            if before_times is not None and after_times is not None and after_times != before_times:
                return {"ok": True, "before_times": before_times, "after_times": after_times, "actions": actions, "times": now}
            if talk.get("ok") and talk.get("changed") and before_times is None:
                return {"ok": True, "before_times": before_times, "after_times": after_times, "actions": actions, "times": now}
            after_ctx = None
            try:
                after_ctx = self._build_task_context()
            except Exception:
                after_ctx = None
            if self._task_advanced(before_ctx, after_ctx):
                return {
                    "ok": True,
                    "before_times": before_times,
                    "after_times": after_times,
                    "actions": actions,
                    "times": now,
                    "after_context": after_ctx.to_dict() if after_ctx is not None else None,
                }
            time.sleep(0.6)
        now = self.detect_shimen_times()
        return {"ok": False, "reason": "submit_timeout", "before_times": before_times, "after_times": now.get("times"), "actions": actions, "times": now}

    def _maybe_buy_item_from_screen(self, item_name: str, quantity: int = 1) -> Dict:
        import vl_locator

        h = w = 0
        located = None
        scrolls = int(os.getenv("ANDROID_SHIMEN_SHOP_SCROLLS", "4") or "4")
        for _ in range(max(1, scrolls)):
            img = self.bot.screenshot_bgr()
            h, w = img.shape[:2]
            try:
                located = vl_locator.locate_text_center(img, item_name, roi=_roi_from_ratio(img, self.shop_roi_ratio))
            except Exception:
                located = None
            if located is not None:
                break
            self.bot.adb.swipe(int(w * 0.70), int(h * 0.70), int(w * 0.70), int(h * 0.40), duration_ms=320)
            time.sleep(0.6)
        if located is None:
            return {"ok": False, "reason": "item_not_found", "item": item_name}
        self.bot.adb.tap(int(located["x"]), int(located["y"]))
        time.sleep(self.bot.step_sleep_s)
        actions = [{"action": "tap_item", "tap": (int(located["x"]), int(located["y"])), "item": item_name}]

        img2 = self.bot.screenshot_bgr()
        buy = None
        for txt in ("购买", "买入", "买"):
            try:
                buy = vl_locator.locate_text_center(img2, txt, roi=(int(w * 0.55), int(h * 0.55), w, h))
            except Exception:
                buy = None
            if buy is not None:
                break
        if buy is not None:
            self.bot.adb.tap(int(buy["x"]), int(buy["y"]))
            time.sleep(self.bot.step_sleep_s)
            actions.append({"action": "tap_buy", "tap": (int(buy["x"]), int(buy["y"]))})
        confirm = self._try_tap_template(self._tpl_confirm, threshold=self.thr_confirm, sleep_after=0.6)
        if confirm is not None:
            actions.append({"action": "confirm", **confirm})
        return {"ok": True, "actions": actions, "quantity": int(quantity)}

    def handle_battle(self, max_wait_s: float = 60.0) -> Dict:
        deadline = time.time() + max(1.0, max_wait_s)
        attacks = 0
        while time.time() < deadline:
            r = self._try_tap_template(self._tpl_attack, threshold=self.thr_attack, sleep_after=0.3)
            if r is not None:
                attacks += 1
                continue
            img = self.bot.screenshot_bgr()
            h, w = img.shape[:2]
            roi_attack = (int(w * 0.72), int(h * 0.45), w, h)
            rt = self._try_tap_text(["攻击"], roi=roi_attack, sleep_after=0.3)
            if rt is not None:
                attacks += 1
                continue
            common = self._handle_common_once()
            if common is not None:
                continue
            time.sleep(0.4)
            if attacks > 0:
                return {"ok": True, "attacks": attacks}
        return {"ok": False, "attacks": attacks, "reason": "timeout"}

    def progress_interaction(self, steps: int = 12) -> Dict:
        actions = []
        for _ in range(max(1, int(steps))):
            common = self._handle_common_once()
            if common is not None:
                actions.append(common)
                continue
            tapped = self.tap_shimen_task()
            if tapped is not None:
                actions.append({"action": "tap_task", **tapped})
                continue
            x, y = self._tap_dialogue_area()
            actions.append({"action": "tap_dialogue", "tap": (x, y)})
        return {"ok": True, "actions": actions}

    def _route_and_interact_for_current_task(self) -> Dict:
        actions = []
        tapped = self.tap_shimen_task()
        if tapped is not None:
            actions.append({"action": "tap_task", **tapped})
        arrival = self.wait_arrived()
        actions.append({"action": "wait_arrived", "result": arrival})
        for _ in range(10):
            common = self._handle_common_once()
            if common is not None:
                actions.append(common)
                if common.get("action") in ("give_text", "give_button_fallback"):
                    break
                continue
            tapped = self.tap_shimen_task()
            if tapped is not None:
                actions.append({"action": "tap_task_again", **tapped})
                continue
            x, y = self._tap_dialogue_area()
            actions.append({"action": "tap_dialogue", "tap": (x, y)})
        return {"ok": True, "actions": actions, "arrival": arrival}

    def _prepare_context_by_task_tracking(self, max_steps: int = 4) -> Dict:
        actions = []
        ctx = self._build_task_context()
        return {"ok": True, "actions": actions, "context": ctx}

    def _direct_purchase_keywords(self, ctx: ShimenTaskContext) -> List[str]:
        """
        买物任务直接寻址，不依赖“帮助/精灵问答”面板。
        先按物品类型做轻量排序，再回退到一组常用店铺。
        """
        item = str(ctx.need_item or "").strip()
        default_keywords = [
            "长安杂货店",
            "长安药店",
            "长安兵器铺",
            "长安布店",
            "长安饰品店",
            "长安乐器店",
        ]
        keyword_env = os.getenv("ANDROID_SHIMEN_DIRECT_PURCHASE_KEYWORDS", "").strip()
        if keyword_env:
            default_keywords = [x.strip() for x in keyword_env.split(",") if x.strip()]

        preferred = []
        # 轻量归类：不是按任务穷举，而是按店铺货类决定优先级。
        if item:
            if re.search(r"(花|草)$", item) or item in ("兰花", "桃花", "玫瑰", "百合", "康乃馨", "牡丹"):
                preferred.extend(["长安杂货店", "长安花店", "长安杂货"])
            elif re.search(r"(药|丹|丸|散|汤|露|香)$", item):
                preferred.extend(["长安药店", "长安药房"])
            elif re.search(r"(剑|刀|枪|斧|锤|爪|鞭|环|双剑|宝珠|法杖|扇)$", item):
                preferred.extend(["长安兵器铺"])
            elif re.search(r"(簪|钗|镯|链|佩|帽|靴|带|衣)$", item):
                preferred.extend(["长安饰品店", "长安布店"])
            elif re.search(r"(琴|笛|箫|唢呐|琵琶|木鱼|编钟|钹)$", item):
                preferred.extend(["长安乐器店"])

        seen = set()
        ordered = []
        for kw in preferred + default_keywords:
            s = str(kw or "").strip()
            if not s or s in seen:
                continue
            seen.add(s)
            ordered.append(s)
        return ordered

    def _navigate_purchase_source(self, ctx: ShimenTaskContext) -> Dict:
        actions = []
        keywords = self._direct_purchase_keywords(ctx)
        for kw in keywords:
            try:
                nav = self.bot.map_search_and_go(kw)
                actions.append({"action": "map_search", "keyword": kw, "result": nav})
                arrival = self.wait_arrived()
                actions.append({"action": "wait_arrived", "result": arrival})
                return {"ok": True, "keyword": kw, "actions": actions, "arrival": arrival}
            except Exception as e:
                actions.append({"action": "map_search_error", "keyword": kw, "error": str(e)})
        return {"ok": False, "reason": "no_purchase_keyword", "keywords": keywords, "actions": actions}

    def _execute_report_strategy(self, ctx: ShimenTaskContext, before_times: Optional[int], cleanup: Dict) -> Dict:
        submit = self._submit_to_master_until_reward(before_times, max_wait_s=float(os.getenv("ANDROID_SHIMEN_SUBMIT_MAX_WAIT_S", "90") or "90"), before_ctx=ctx)
        return {"ok": bool(submit.get("ok")), "cleanup": cleanup, "reason": "report_to_master", "context": ctx.to_dict(), "submit": submit}

    def _execute_deliver_strategy(self, ctx: ShimenTaskContext, before_times: Optional[int], cleanup: Dict) -> Dict:
        routed = self._route_and_interact_for_current_task()
        submit = self._submit_to_master_until_reward(before_times, max_wait_s=float(os.getenv("ANDROID_SHIMEN_SUBMIT_MAX_WAIT_S", "90") or "90"), before_ctx=ctx)
        return {
            "ok": bool(submit.get("ok")),
            "cleanup": cleanup,
            "reason": "deliver_then_submit",
            "context": ctx.to_dict(),
            "delivery": routed,
            "submit": submit,
        }

    def _execute_buy_item_strategy(self, ctx: ShimenTaskContext, before_times: Optional[int], cleanup: Dict) -> Dict:
        ctx2 = ctx
        prepared_out = {"ok": True, "actions": [], "context": ctx2.to_dict(), "mode": "direct_addressing"}
        nav = self._navigate_purchase_source(ctx2)
        if not nav.get("ok"):
            return {
                "ok": False,
                "cleanup": cleanup,
                "reason": "buy_nav_failed",
                "context": ctx2.to_dict(),
                "prepare": prepared_out,
                "nav": nav,
            }
        buy = self._maybe_buy_item_from_screen(ctx2.need_item, ctx2.need_quantity) if ctx2.need_item else {"ok": False, "reason": "no_item"}
        if not buy.get("ok"):
            return {
                "ok": False,
                "cleanup": cleanup,
                "reason": "buy_item_failed",
                "context": ctx2.to_dict(),
                "prepare": prepared_out,
                "nav": nav,
                "buy": buy,
            }
        submit = self._submit_to_master_until_reward(
            before_times,
            max_wait_s=float(os.getenv("ANDROID_SHIMEN_SUBMIT_MAX_WAIT_S", "90") or "90"),
            prefer_direct_master=True,
            before_ctx=ctx2,
        )
        return {
            "ok": bool(submit.get("ok")),
            "cleanup": cleanup,
            "reason": "buy_and_submit",
            "context": ctx2.to_dict(),
            "prepare": prepared_out,
            "nav": nav,
            "buy": buy,
            "submit": submit,
        }

    def _execute_generic_strategy(self, ctx: ShimenTaskContext, before_times: Optional[int], cleanup: Dict) -> Dict:
        tap_task = self.tap_shimen_task()
        arrival = self.wait_arrived() if tap_task is not None else None
        interaction = self.progress_interaction(steps=int(os.getenv("ANDROID_SHIMEN_INTERACTION_STEPS", "10") or "10"))
        battle = self.handle_battle(max_wait_s=float(os.getenv("ANDROID_SHIMEN_BATTLE_MAX_WAIT_S", "45") or "45"))
        submit = self._submit_to_master_until_reward(before_times, max_wait_s=float(os.getenv("ANDROID_SHIMEN_SUBMIT_MAX_WAIT_S", "90") or "90"), before_ctx=ctx)
        return {
            "ok": bool(submit.get("ok")),
            "cleanup": cleanup,
            "reason": "generic_progress",
            "context": ctx.to_dict(),
            "tap_shimen_task": tap_task,
            "arrival": arrival,
            "interaction": interaction,
            "battle": battle,
            "submit": submit,
        }

    def run_once(self) -> Dict:
        try:
            startup_cleanup = self.cleanup_startup_popups(max_steps=6)
            cleanup = {"startup": startup_cleanup, "ui_visible": self.ensure_ui_visible()}
            before_times = None
            try:
                before_times = self.detect_shimen_times().get("times")
            except Exception:
                before_times = None
            ctx = self._build_task_context()
            if ctx.family == "report":
                return self._execute_report_strategy(ctx, before_times, cleanup)
            if ctx.family == "deliver":
                return self._execute_deliver_strategy(ctx, before_times, cleanup)
            if ctx.family == "buy_item":
                return self._execute_buy_item_strategy(ctx, before_times, cleanup)
            return self._execute_generic_strategy(ctx, before_times, cleanup)
        except Exception as e:
            return {"ok": False, "reason": "exception", "error": str(e)}

    def run(self, rounds: int = 10) -> Dict:
        results = []
        started = None
        try:
            started = self.detect_shimen_times().get("times")
        except Exception:
            started = None
        for _ in range(max(1, int(rounds))):
            before = None
            try:
                before = self.detect_shimen_times().get("times")
            except Exception:
                before = None
            r = self.run_once()
            after = None
            try:
                after = self.detect_shimen_times().get("times")
            except Exception:
                after = None
            r["before_times"] = before
            r["after_times"] = after
            results.append(r)
            if not r.get("ok"):
                break
        ended = None
        try:
            ended = self.detect_shimen_times().get("times")
        except Exception:
            ended = None
        overview = None
        try:
            overview = self.open_task_overview_and_read_done()
        except Exception:
            overview = None
        return {"ok": True, "rounds": rounds, "started_times": started, "ended_times": ended, "overview": overview, "results": results}


def main() -> None:
    sys_util.load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", type=str, default="")
    ap.add_argument("--rounds", type=int, default=int(os.getenv("ANDROID_SHIMEN_ROUNDS", "10") or "10"))
    ap.add_argument("--replay-dir", type=str, default="")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--use-vl", action="store_true")
    args = ap.parse_args()
    if args.serial:
        os.environ["ADB_SERIAL"] = str(args.serial).strip()
    if args.debug:
        os.environ["DEBUG"] = "1"
    if args.use_vl:
        os.environ["ANDROID_SHIMEN_USE_VL"] = "1"
    if args.replay_dir:
        from replay_adb import ReplayAdbClient, list_images_in_dir

        imgs = list_images_in_dir(args.replay_dir, name_contains="android_screencap")
        adb = ReplayAdbClient(imgs, loop=True, sleep_s=0.0)
        bot = AndroidShimenBot(bot=AndroidMhxyBot(adb=adb))
    else:
        bot = AndroidShimenBot()
    result = bot.run(rounds=args.rounds)
    for i, r in enumerate(result.get("results", []), start=1):
        print(f"round {i}: ok={r.get('ok')} reason={r.get('reason')} times={r.get('before_times')}->{r.get('after_times')}")
    print(f"shimen_times: started={result.get('started_times')} ended={result.get('ended_times')}")
    ov = result.get("overview") or {}
    if ov:
        print(f"task_overview_done: {ov.get('done')} raw={ov.get('raw_text')}")


if __name__ == "__main__":
    main()
