import argparse
import io
import os
import re
import time
from typing import Dict, Optional, Tuple
from unittest import result

import cv2
import numpy as np
from PIL import Image

import siliflow_client
import sys_util
from adb_util import AdbClient
from image_matcher import match_template


def _parse_roi(roi_text: str) -> Tuple[int, int, int, int]:
    parts = [x.strip() for x in roi_text.split(",")]
    if len(parts) != 4:
        raise RuntimeError("MHXY_MAP_ROI 格式错误，期望 x1,y1,x2,y2")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError("MHXY_MAP_ROI 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("MHXY_MAP_ROI 数值无效，要求 x2>x1,y2>y1")
    return x1, y1, x2, y2


def _bgr_to_pil(img_bgr: np.ndarray) -> Image.Image:
    if img_bgr is None:
        raise RuntimeError("空图像")
    if len(img_bgr.shape) == 3 and img_bgr.shape[2] == 3:
        return Image.fromarray(img_bgr[:, :, ::-1])
    if len(img_bgr.shape) == 3 and img_bgr.shape[2] == 4:
        return Image.fromarray(img_bgr[:, :, [2, 1, 0, 3]])
    return Image.fromarray(img_bgr)


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pick_best_location(locations):
    if not locations:
        return None
    best = locations[0]
    for loc in locations[1:]:
        if loc[1] > best[1]:
            best = loc
    return best


def _template_center_from_top_left(template_path: str, top_left: Tuple[int, int], extra_offset: Tuple[int, int]) -> Tuple[int, int]:
    tpl = cv2.imread(template_path)
    if tpl is None:
        raise RuntimeError(f"模板读取失败: {template_path}")
    h, w = tpl.shape[:2]
    cx = int(top_left[0] + w / 2 + extra_offset[0])
    cy = int(top_left[1] + h / 2 + extra_offset[1])
    return cx, cy


class AndroidMhxyBot:
    def __init__(self, adb: Optional[AdbClient] = None) -> None:
        self.adb = adb or AdbClient()
        self.map_roi_text = os.getenv("MHXY_MAP_ROI", "").strip()

        self.tpl_map_button = os.getenv("ANDROID_TPL_MAP_BUTTON", "assets/android/map/map_button.jpg").strip() or "assets/android/map/map_button.jpg"
        self.tpl_map_button_2 = os.getenv("ANDROID_TPL_MAP_BUTTON_2", "assets/android/map/map_button2.png").strip() or "assets/android/map/map_button2.png"
        self.tpl_map_search_icon = os.getenv("ANDROID_TPL_MAP_SEARCH_ICON", "assets/android/map/map_search_icon.png").strip() or "assets/android/map/map_search_icon.png"
        self.tpl_map_input_icon = os.getenv("ANDROID_TPL_MAP_INPUT_ICON", "assets/android/map/map_input_icon.png").strip() or "assets/android/map/map_input_icon.png"
        self.tpl_map_go = os.getenv("ANDROID_TPL_MAP_GO", "assets/android/map/map_go.jpg").strip() or "assets/android/map/map_go.jpg"
        self.tpl_map_exit = os.getenv("ANDROID_TPL_MAP_EXIT", "assets/android/map/map_exit.jpg").strip() or "assets/android/map/map_exit.jpg"
        self.tpl_map_dianxiaoer = os.getenv("ANDROID_TPL_MAP_DIANXIAOER", "assets/android/map/map_dianxiaoer.png").strip() or "assets/android/map/map_dianxiaoer.png"
        self.tpl_map_on_the_way = os.getenv("ANDROID_TPL_MAP_ON_THE_WAY", "assets/android/map/map_on_the_way.png").strip() or "assets/android/map/map_on_the_way.png"
        self.tpl_menu_daoju = os.getenv("ANDROID_TPL_MENU_DAOJU", "assets/android/memu/daoju.jpg").strip() or "assets/android/memu/daoju.jpg"
        self.tpl_prop_changan_flag = os.getenv("ANDROID_TPL_PROP_CHANGAN_FLAG", "assets/android/daoju/changandaobiaoqi.png").strip() or "assets/android/daoju/changandaobiaoqi.png"
        self.tpl_prop_use = os.getenv("ANDROID_TPL_PROP_USE", "assets/android/daoju/jiemian/shiyong.png").strip() or "assets/android/daoju/jiemian/shiyong.png"
        self.tpl_map_teleport_point = os.getenv("ANDROID_TPL_MAP_TELEPORT_POINT", "assets/android/map/daobiaoqiditu/chuansongdian.png").strip() or "assets/android/map/daobiaoqiditu/chuansongdian.png"
        self.tpl_baotu_receive_task = os.getenv("ANDROID_TPL_BAOTU_RECEIVE_TASK", "assets/android/baotu/tingtingwufang.png").strip() or "assets/android/baotu/tingtingwufang.png"
        self.tpl_changan_hotel_door = os.getenv("ANDROID_TPL_CHANGAN_HOTEL_DOOR", "assets/android/changancheng/jiudianmenkou.png").strip() or "assets/android/changancheng/jiudianmenkou.png"
        self.tpl_system_close_guide = os.getenv("ANDROID_TPL_SYSTEM_CLOSE_GUIDE", "assets/android/system/guanbizhiyin.png").strip() or "assets/android/system/guanbizhiyin.png"
        self.tpl_system_close_task = os.getenv("ANDROID_TPL_SYSTEM_CLOSE_TASK", "assets/android/system/close_task.jpg").strip() or "assets/android/system/close_task.jpg"
        self.tpl_system_hide_dialog = os.getenv("ANDROID_TPL_SYSTEM_HIDE_DIALOG", "assets/android/system/yincangduihua.png").strip() or "assets/android/system/yincangduihua.png"
        self.tpl_system_auto_attack_shrink = os.getenv("ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK", "assets/android/system/zidonggongjisuoxiao.png").strip() or "assets/android/system/zidonggongjisuoxiao.png"
        self.tpl_system_expand = os.getenv("ANDROID_TPL_SYSTEM_EXPAND", "assets/android/system/expand.jpg").strip() or "assets/android/system/expand.jpg"
        self.tpl_system_hide_ui = os.getenv("ANDROID_TPL_SYSTEM_HIDE_UI", "assets/android/system/yincangjiemian.jpg").strip() or "assets/android/system/yincangjiemian.jpg"
        self.tpl_system_hide_player = os.getenv("ANDROID_TPL_SYSTEM_HIDE_PLAYER", "assets/android/system/yincangwanjia.jpg").strip() or "assets/android/system/yincangwanjia.jpg"
        self.tpl_system_hide_ui_disable = os.getenv("ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE", "assets/android/system/yincangjiemian_disable.png").strip() or "assets/android/system/yincangjiemian_disable.png"
        self.tpl_system_hide_player_disable = os.getenv("ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE", "assets/android/system/yincangwanjia_disable.png").strip() or "assets/android/system/yincangwanjia_disable.png"
        self.tpl_system_back = os.getenv("ANDROID_TPL_SYSTEM_BACK", "assets/android/system/back.jpg").strip() or "assets/android/system/back.jpg"
        self.tpl_npc_dianxiaoer_1 = os.getenv("ANDROID_TPL_NPC_DIANXIAOER_1", "assets/android/npc/dianxiaoer1.png").strip() or "assets/android/npc/dianxiaoer1.png"
        self.tpl_npc_dianxiaoer_2 = os.getenv("ANDROID_TPL_NPC_DIANXIAOER_2", "assets/android/npc/dianxiaoer2.png").strip() or "assets/android/npc/dianxiaoer2.png"
        self.tpl_npc_dianxiaoer_3 = os.getenv("ANDROID_TPL_NPC_DIANXIAOER_3", "assets/android/npc/dianxiaoer3.png").strip() or "assets/android/npc/dianxiaoer3.png"

        self.match_threshold = float(os.getenv("ANDROID_MATCH_THRESHOLD", "0.8").strip() or "0.8")
        self.step_sleep_s = float(os.getenv("ANDROID_STEP_SLEEP_S", "0.4").strip() or "0.4")
        self.coord_ocr_engine = (os.getenv("ANDROID_COORD_OCR_ENGINE", "paddle").strip() or "paddle").lower()
        self.coord_roi_text = os.getenv("ANDROID_COORD_ROI", "").strip()
        self._tpl_wh_cache: Dict[str, Tuple[int, int]] = {}
        
    def screenshot_bgr(self) -> np.ndarray:
        img = self.adb.screenshot_bgr()
        return img

    def detect_current_map(self) -> Dict:
        if not self.map_roi_text:
            raise RuntimeError("缺少 MHXY_MAP_ROI，请在 .env 配置，例如 0,0,120,120")
        x1, y1, x2, y2 = _parse_roi(self.map_roi_text)
        img_bgr = self.screenshot_bgr()
        pil_img = _bgr_to_pil(img_bgr)
        cropped = pil_img.crop((x1, y1, x2, y2))
        sys_util.save_debug_image(cropped, "android_map_roi_cropped")
        png_bytes = _pil_to_png_bytes(cropped)
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        map_name = str(ocr_result.get("content", "")).strip()
        print(f"ocr_result: {ocr_result}, map_name: {map_name}")
        return {"map_name": map_name, "raw_ocr": ocr_result, "roi": [x1, y1, x2, y2]}

    def _match_once(self, img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None):
        thr = self.match_threshold if threshold is None else threshold
        ok, _, locations = match_template(img_bgr, template_path, threshold=thr, find_all=True)
        if not ok or not locations:
            return None
        return _pick_best_location(locations)

    def _tap_template(self, img_bgr: np.ndarray, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        best = self._match_once(img_bgr, template_path, threshold=threshold)
        if best is None:
            raise RuntimeError(f"模板匹配失败: {template_path}")
        (top_left, _) = best
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        self.adb.tap(cx, cy)
        return cx, cy

    def _tap(self, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        pt = self._tap_template(img_bgr, template_path, threshold=threshold, extra_offset=extra_offset)
        time.sleep(self.step_sleep_s)
        return pt

    def _try_tap(self, template_path: str, threshold: Optional[float] = None, extra_offset: Tuple[int, int] = (0, 0)) -> Optional[Tuple[int, int]]:
        img_bgr = self.screenshot_bgr()
        best = self._match_once(img_bgr, template_path, threshold=threshold)
        if best is None:
            return None
        (top_left, _) = best
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        self.adb.tap(cx, cy)
        time.sleep(self.step_sleep_s)
        return cx, cy

    def cleanup_desktop(self) -> Dict:
        thr_close_guide = float(os.getenv("ANDROID_THR_SYSTEM_CLOSE_GUIDE", str(self.match_threshold)) or self.match_threshold)
        thr_close_task = float(os.getenv("ANDROID_THR_SYSTEM_CLOSE_TASK", str(self.match_threshold)) or self.match_threshold)
        thr_hide_dialog = float(os.getenv("ANDROID_THR_SYSTEM_HIDE_DIALOG", str(self.match_threshold)) or self.match_threshold)
        thr_auto_attack_shrink = float(os.getenv("ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK", str(self.match_threshold)) or self.match_threshold)
        thr_expand = float(os.getenv("ANDROID_THR_SYSTEM_EXPAND", str(self.match_threshold)) or self.match_threshold)
        thr_hide_ui_disable = float(os.getenv("ANDROID_THR_SYSTEM_HIDE_UI_DISABLE", str(self.match_threshold)) or self.match_threshold)
        thr_hide_player_disable = float(os.getenv("ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE", str(self.match_threshold)) or self.match_threshold)
        thr_back = float(os.getenv("ANDROID_THR_SYSTEM_BACK", str(self.match_threshold)) or self.match_threshold)

        p_close_guide = self._try_tap(self.tpl_system_close_guide, threshold=thr_close_guide)
        p_close_task = self._try_tap(self.tpl_system_close_task, threshold=thr_close_task)
        p_hide_dialog = self._try_tap(self.tpl_system_hide_dialog, threshold=thr_hide_dialog)
        p_auto_attack_shrink = self._try_tap(self.tpl_system_auto_attack_shrink, threshold=thr_auto_attack_shrink)

        p_expand = self._try_tap(self.tpl_system_expand, threshold=thr_expand)
        p_hide_ui_disable = self._try_tap(self.tpl_system_hide_ui_disable, threshold=thr_hide_ui_disable) if p_expand is not None else None
        p_hide_player_disable = self._try_tap(self.tpl_system_hide_player_disable, threshold=thr_hide_player_disable) if p_expand is not None else None

        p_back = self._try_tap(self.tpl_system_back, threshold=thr_back) if p_expand is not None else None

        return {
            "tap_close_guide": p_close_guide,
            "tap_close_task": p_close_task,
            "tap_hide_dialog": p_hide_dialog,
            "tap_auto_attack_shrink": p_auto_attack_shrink,
            "tap_expand": p_expand,
            "tap_hide_ui_disable": p_hide_ui_disable,
            "tap_hide_player_disable": p_hide_player_disable,
            "tap_back": p_back,
        }

    def _get_template_wh(self, template_path: str) -> Tuple[int, int]:
        cached = self._tpl_wh_cache.get(template_path)
        if cached is not None:
            return cached
        tpl = cv2.imread(template_path)
        if tpl is None:
            raise RuntimeError(f"模板读取失败: {template_path}")
        h, w = tpl.shape[:2]
        self._tpl_wh_cache[template_path] = (w, h)
        return w, h

    def _match_best_of_templates(self, img_bgr: np.ndarray, template_paths, threshold: float):
        best = None
        for tpl in template_paths:
            ok, _, locations = match_template(img_bgr, tpl, threshold=threshold, find_all=True)
            if not ok or not locations:
                continue
            loc = _pick_best_location(locations)
            if loc is None:
                continue
            (top_left, conf) = loc
            if best is None or conf > best["confidence"]:
                best = {"template": tpl, "top_left": top_left, "confidence": conf}
        return best

    def _match_first_of_templates(self, img_bgr: np.ndarray, template_paths, threshold: float):
        for tpl in template_paths:
            ok, _, locations = match_template(img_bgr, tpl, threshold=threshold, find_all=True)
            if not ok or not locations:
                continue
            loc = _pick_best_location(locations)
            if loc is None:
                continue
            (top_left, conf) = loc
            return {"template": tpl, "top_left": top_left, "confidence": conf}
        return None

    def _tap_matched_center(self, img_bgr: np.ndarray, template_path: str, top_left: Tuple[int, int], extra_offset: Tuple[int, int] = (0, 0)) -> Tuple[int, int]:
        cx, cy = _template_center_from_top_left(template_path, top_left, extra_offset=extra_offset)
        try:
            dbg = img_bgr.copy()
            cv2.drawMarker(dbg, (int(cx), int(cy)), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=40, thickness=2)
            sys_util.save_debug_image(dbg, f"android_tap_{os.path.basename(template_path)}_{cx}_{cy}")
        except Exception:
            pass
        self.adb.tap(cx, cy)
        return cx, cy

    def match_best(self, template_paths, threshold: float = 0.8) -> Optional[Dict]:
        img_bgr = self.screenshot_bgr()
        return self._match_best_of_templates(img_bgr, template_paths, threshold=threshold)

    def try_tap_best(self, template_paths, threshold: float = 0.8, extra_offset: Tuple[int, int] = (0, 0), sleep_after: Optional[float] = None) -> Optional[Dict]:
        img_bgr = self.screenshot_bgr()
        matched = self._match_best_of_templates(img_bgr, template_paths, threshold=threshold)
        if matched is None:
            return None
        tpl = str(matched["template"])
        top_left = matched["top_left"]
        pt = self._tap_matched_center(img_bgr, tpl, top_left, extra_offset=extra_offset)
        time.sleep(self.step_sleep_s if sleep_after is None else float(sleep_after))
        return {"template": tpl, "top_left": top_left, "confidence": float(matched["confidence"]), "tap": pt}

    def tap_map_button(self, threshold: float = 0.6) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        matched = self._match_best_of_templates(
            img_bgr,
            [self.tpl_map_button, self.tpl_map_button_2],
            threshold=threshold,
        )
        if matched is None:
            raise RuntimeError("地图按钮模板匹配失败")
        return self._tap_matched_center(img_bgr, str(matched["template"]), matched["top_left"])

    def talk_to_dianxiaoer(self) -> Dict:
        cleanup = self.cleanup_desktop()
        img_bgr = self.screenshot_bgr()
        matched = self._match_best_of_templates(
            img_bgr,
            [self.tpl_npc_dianxiaoer_1, self.tpl_npc_dianxiaoer_2, self.tpl_npc_dianxiaoer_3],
            threshold=0.5,
        )
        if matched is None:
            return {"ok": False, "reason": "npc_not_found", "cleanup": cleanup}

        tpl = str(matched["template"])
        top_left = matched["top_left"]
        conf = float(matched["confidence"])
        w, h = self._get_template_wh(tpl)
        margin = max(5, int(w * 0.1))
        margin = min(margin, max(1, w - 1))
        x_edge = int(top_left[0] + margin)
        y_edge = int(top_left[1] + h / 2)
        x_center = int(top_left[0] + w / 2)
        y_center = int(top_left[1] + h / 2)

        self.adb.tap(x_edge, y_edge)
        time.sleep(2.0)
        self.adb.tap(x_center, y_center)
        time.sleep(self.step_sleep_s)
        return {
            "ok": True,
            "cleanup": cleanup,
            "template": tpl,
            "confidence": conf,
            "tap_edge": (x_edge, y_edge),
            "tap_center": (x_center, y_center),
        }

    def map_search_and_go(self, keyword: str, result_roi: Optional[Tuple[int, int, int, int]] = None) -> Dict:
        import vl_locator

        kw = str(keyword or "").strip()
        if not kw:
            raise RuntimeError("keyword 不能为空")

        def _tap_text_once(candidates, roi: Optional[Tuple[int, int, int, int]] = None):
            img_local = self.screenshot_bgr()
            for txt in candidates:
                try:
                    located_local = vl_locator.locate_text_center(img_local, str(txt), roi=roi)
                except Exception:
                    located_local = None
                if located_local is None:
                    continue
                x_local = int(located_local["x"])
                y_local = int(located_local["y"])
                self.adb.tap(x_local, y_local)
                time.sleep(self.step_sleep_s)
                return (x_local, y_local)
            return None

        thr_search_icon = float(os.getenv("ANDROID_THR_MAP_SEARCH_ICON", str(self.match_threshold)) or self.match_threshold)
        thr_input_icon = float(os.getenv("ANDROID_THR_MAP_INPUT_ICON", str(self.match_threshold)) or self.match_threshold)
        thr_go = float(os.getenv("ANDROID_THR_MAP_GO", "0.6") or "0.6")

        p1 = self.tap_map_button(threshold=0.6)
        time.sleep(self.step_sleep_s)
        try:
            p2 = self._tap(self.tpl_map_search_icon, threshold=thr_search_icon)
        except Exception:
            img0 = self.screenshot_bgr()
            h0, w0 = img0.shape[:2]
            roi_top = (int(w0 * 0.50), 0, w0, int(h0 * 0.24))
            p2 = _tap_text_once(["搜索", "查找"], roi=roi_top)
            if p2 is None:
                p2 = (int(w0 * 0.86), int(h0 * 0.10))
                self.adb.tap(*p2)
                time.sleep(self.step_sleep_s)
        try:
            p3 = self._tap(self.tpl_map_input_icon, threshold=thr_input_icon)
        except Exception:
            img1 = self.screenshot_bgr()
            h1, w1 = img1.shape[:2]
            p3 = _tap_text_once(["搜索", "输入"], roi=(int(w1 * 0.30), 0, int(w1 * 0.92), int(h1 * 0.28)))
            if p3 is None:
                p3 = (int(w1 * 0.62), int(h1 * 0.11))
                self.adb.tap(*p3)
                time.sleep(self.step_sleep_s)

        adb_ime = os.getenv("ANDROID_ADB_IME_ID", "com.android.adbkeyboard/.AdbIME").strip() or "com.android.adbkeyboard/.AdbIME"
        sogou_ime = os.getenv("ANDROID_SOGOU_IME_ID", "com.sohu.inputmethod.sogou.xiaomi/.SogouIME").strip() or "com.sohu.inputmethod.sogou.xiaomi/.SogouIME"
        self.adb.ime_set(adb_ime)
        time.sleep(self.step_sleep_s)
        self.adb.adbkeyboard_input_text(kw)
        time.sleep(self.step_sleep_s)
        self.adb.keyevent(66)
        time.sleep(self.step_sleep_s)
        self.adb.ime_set(sogou_ime)
        time.sleep(self.step_sleep_s)

        img = self.screenshot_bgr()
        located = None
        try:
            located = vl_locator.locate_text_center(img, kw, roi=result_roi)
        except Exception:
            located = None
        p4 = None
        if located is not None:
            x = int(located["x"])
            y = int(located["y"])
            self.adb.tap(x, y)
            p4 = (x, y)
            time.sleep(self.step_sleep_s)
        else:
            h, w = img.shape[:2]
            x = int(w * 0.55)
            y = int(h * 0.35)
            self.adb.tap(x, y)
            p4 = (x, y)
            time.sleep(self.step_sleep_s)

        go = self.try_tap_best([self.tpl_map_go, self.tpl_map_on_the_way], threshold=thr_go)
        if go is None:
            img2 = self.screenshot_bgr()
            h2, w2 = img2.shape[:2]
            roi_go = (int(w2 * 0.58), int(h2 * 0.18), w2, int(h2 * 0.92))
            p5 = _tap_text_once(["前往", "在路上", "寻路"], roi=roi_go)
            go = {"template": "vl_text", "tap": p5} if p5 is not None else None
        return {"ok": True, "tap_map": p1, "tap_search": p2, "tap_input": p3, "tap_result": p4, "tap_go": go, "keyword": kw}

    def _ocr_text_from_roi_paddle(self, img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> str:
        x1, y1, x2, y2 = roi
        pil_img = _bgr_to_pil(img_bgr)
        cropped = pil_img.crop((x1, y1, x2, y2))
        sys_util.save_debug_image(cropped, "android_coord_roi_cropped")
        png_bytes = _pil_to_png_bytes(cropped)
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        return str(ocr_result.get("content", "")).strip()

    def _ocr_text_from_roi_ddddocr(self, img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> str:
        import importlib

        mod = importlib.import_module("ddddocr_util")
        return str(mod.ocr_region(img_bgr, roi)).strip()

    def _parse_coord_text(self, text: str) -> Optional[Tuple[int, int]]:
        s = str(text or "").strip()
        if not s:
            return None
        m = re.search(r"(\d{1,3})\s*[,，]\s*(\d{1,3})", s)
        if m:
            return int(m.group(1)), int(m.group(2))
        if "(" in s or "（" in s or ")" in s or "）" in s:
            nums = re.findall(r"\d+", s)
            if len(nums) >= 2:
                return int(nums[0]), int(nums[1])
        return None

    def detect_coord_by_roi(self) -> Dict:
        if not self.coord_roi_text:
            raise RuntimeError("缺少 ANDROID_COORD_ROI")
        roi = _parse_roi(self.coord_roi_text)
        img_bgr = self.screenshot_bgr()
        engine = self.coord_ocr_engine
        text = ""
        used_engine = engine
        if engine == "ddddocr":
            try:
                text = self._ocr_text_from_roi_ddddocr(img_bgr, roi)
            except Exception:
                used_engine = "paddle"
                text = self._ocr_text_from_roi_paddle(img_bgr, roi)
        else:
            text = self._ocr_text_from_roi_paddle(img_bgr, roi)
        coord = self._parse_coord_text(text)
        return {"coord": coord, "raw_text": text, "engine": used_engine, "roi": list(roi)}

    def wait_until_arrived_by_coord(self) -> Dict:
        max_wait_s = float(os.getenv("ANDROID_ARRIVAL_MAX_WAIT_S", "60") or "60")
        interval_s = float(os.getenv("ANDROID_ARRIVAL_CHECK_INTERVAL_S", "1") or "1")
        stable_need = int(os.getenv("ANDROID_ARRIVAL_STABLE_COUNT", "2") or "2")
        deadline = time.time() + max(1.0, max_wait_s)
        stable = 0
        last = None
        samples = 0

        while time.time() < deadline:
            r = self.detect_coord_by_roi()
            samples += 1
            coord = r.get("coord")
            if coord is not None and coord == last:
                stable += 1
            else:
                stable = 1 if coord is not None else 0
                last = coord
            if stable >= stable_need and last is not None:
                return {"arrived": True, "coord": last, "samples": samples}
            time.sleep(max(0.1, interval_s))

        return {"arrived": False, "coord": last, "samples": samples}

    def fly_to_hotel(self) -> Dict:
        thr_menu_daoju = float(os.getenv("ANDROID_THR_MENU_DAOJU", str(self.match_threshold)) or self.match_threshold)
        thr_prop_changan_flag = float(os.getenv("ANDROID_THR_PROP_CHANGAN_FLAG", str(self.match_threshold)) or self.match_threshold)
        thr_prop_use = float(os.getenv("ANDROID_THR_PROP_USE", str(self.match_threshold)) or self.match_threshold)
        thr_teleport_point = float(os.getenv("ANDROID_THR_MAP_TELEPORT_POINT", str(self.match_threshold)) or self.match_threshold)

        p_menu_daoju = self._tap(self.tpl_menu_daoju, threshold=thr_menu_daoju)
        p_changan_flag = self._tap(self.tpl_prop_changan_flag, threshold=thr_prop_changan_flag)
        p_use = self._tap(self.tpl_prop_use, threshold=thr_prop_use)

        target_x = int(os.getenv("ANDROID_TELEPORT_TARGET_X", "1640") or "1640")
        target_y = int(os.getenv("ANDROID_TELEPORT_TARGET_Y", "500") or "500")

        img_bgr = self.screenshot_bgr()
        ok, _, locations = match_template(img_bgr, self.tpl_map_teleport_point, threshold=thr_teleport_point, find_all=True)
        if not ok or not locations:
            return {
                "ok": False,
                "reason": "teleport_point_not_found",
                "tap_menu_daoju": p_menu_daoju,
                "tap_changan_flag": p_changan_flag,
                "tap_use": p_use,
            }

        best = None
        for (top_left, conf) in locations:
            cx, cy = _template_center_from_top_left(self.tpl_map_teleport_point, top_left, extra_offset=(0, 0))
            dx = cx - target_x
            dy = cy - target_y
            dist2 = dx * dx + dy * dy
            item = {"top_left": top_left, "confidence": float(conf), "center": (cx, cy), "dist2": int(dist2)}
            if best is None or item["dist2"] < best["dist2"]:
                best = item

        tap_teleport = self._tap_matched_center(img_bgr, self.tpl_map_teleport_point, best["top_left"])
        time.sleep(self.step_sleep_s)

        return {
            "ok": True,
            "tap_menu_daoju": p_menu_daoju,
            "tap_changan_flag": p_changan_flag,
            "tap_use": p_use,
            "target": (target_x, target_y),
            "teleport_point_best": best,
            "tap_teleport": tap_teleport,
            "teleport_point_count": int(len(locations)),
        }
    
    def recieve_baotu_task(self) -> Dict:
        max_retry = 10
        thr_receive_task = float(os.getenv("ANDROID_THR_BAOTU_RECEIVE_TASK", str(self.match_threshold)) or self.match_threshold)
        attempts = []

        for i in range(1, max_retry + 1):
            step = self.go_to_xiaoer()
            img_bgr = self.screenshot_bgr()
            best_task = self._match_once(img_bgr, self.tpl_baotu_receive_task, threshold=thr_receive_task)
            if best_task is not None:
                (top_left, conf) = best_task
                p_task = self._tap_template(img_bgr, self.tpl_baotu_receive_task, threshold=thr_receive_task)
                return {
                    "ok": True,
                    "attempt": i,
                    "step": step,
                    "receive_task": {"template": self.tpl_baotu_receive_task, "top_left": top_left, "confidence": float(conf), "tap": p_task},
                }
            attempts.append({"attempt": i, "step": step, "receive_task": None})

        raise RuntimeError(f"领取宝图任务失败，重试超过{max_retry}次: {attempts}")

    def go_to_xiaoer(self) -> Dict:
        thr_expand = float(os.getenv("ANDROID_THR_SYSTEM_EXPAND", str(self.match_threshold)) or self.match_threshold)
        thr_xiaoer = float(os.getenv("ANDROID_THR_NPC_XIAOER", "0.4") or "0.4")
        thr_back = float(os.getenv("ANDROID_THR_SYSTEM_BACK", str(self.match_threshold)) or self.match_threshold)

        p_expand = self._try_tap(self.tpl_system_expand, threshold=thr_expand)

        img_bgr = self.screenshot_bgr()
        matched = self._match_first_of_templates(img_bgr, [self.tpl_npc_dianxiaoer_1, self.tpl_npc_dianxiaoer_2, self.tpl_npc_dianxiaoer_3], threshold=thr_xiaoer)
        if matched is None:
            return {"ok": False, "reason": "npc_not_found", "tap_expand": p_expand}

        tpl = str(matched["template"])
        top_left = matched["top_left"]
        conf = float(matched["confidence"])
        p_center = self._tap_matched_center(img_bgr, tpl, top_left)
        p_back = self._tap(self.tpl_system_back, threshold=thr_back)
        time.sleep(self.step_sleep_s)

        return {
            "ok": True,
            "tap_expand": p_expand,
            "template": tpl,
            "confidence": conf,
            "top_left": top_left,
            "tap_center": p_center,
            "tap_back": p_back,
        }

    def enter_hotel(self) -> Dict:
        thr_expand = float(os.getenv("ANDROID_THR_SYSTEM_EXPAND", str(self.match_threshold)) or self.match_threshold)
        thr_hotel_door = float(os.getenv("ANDROID_THR_CHANGAN_HOTEL_DOOR", str(self.match_threshold)) or self.match_threshold)
        thr_back = float(os.getenv("ANDROID_THR_SYSTEM_BACK", str(self.match_threshold)) or self.match_threshold)

        p_expand = self._tap(self.tpl_system_expand, threshold=thr_expand)
        p_hotel_door = self._tap(self.tpl_changan_hotel_door, threshold=thr_hotel_door)
        p_back = self._tap(self.tpl_system_back, threshold=thr_back)
        return {"ok": True, "tap_expand": p_expand, "tap_hotel_door": p_hotel_door, "tap_back": p_back}

    def go_to_dianxiaoer_in_changan(self) -> Dict:
        detected = self.detect_current_map()
        map_name = str(detected.get("map_name", "")).strip()
        if "长安城" not in map_name:
            return {"ok": False, "reason": "not_in_changan", "map_name": map_name, "detected": detected}

        # thr_map_button = float(os.getenv("ANDROID_THR_MAP_BUTTON", str(self.match_threshold)) or self.match_threshold)
        thr_search_icon = float(os.getenv("ANDROID_THR_MAP_SEARCH_ICON", str(self.match_threshold)) or self.match_threshold)
        thr_input_icon = float(os.getenv("ANDROID_THR_MAP_INPUT_ICON", str(self.match_threshold)) or self.match_threshold)
        thr_dianxiaoer = float(os.getenv("ANDROID_THR_MAP_DIANXIAOER", str(self.match_threshold)) or self.match_threshold)
        thr_on_the_way = float(os.getenv("ANDROID_THR_MAP_ON_THE_WAY", str(self.match_threshold)) or self.match_threshold)

        p1 = self.tap_map_button(threshold=0.6)
        time.sleep(self.step_sleep_s)
        p2 = self._tap(self.tpl_map_search_icon, threshold=thr_search_icon)
        used_typed_search = False
        p3 = None
        img_bgr = self.screenshot_bgr()
        best = self._match_once(img_bgr, self.tpl_map_dianxiaoer, threshold=thr_dianxiaoer)
        if best is not None:
            p4 = self._tap_template(img_bgr, self.tpl_map_dianxiaoer, threshold=thr_dianxiaoer)
            time.sleep(self.step_sleep_s)
        else:
            used_typed_search = True
            p3 = self._tap(self.tpl_map_input_icon, threshold=thr_input_icon)
            adb_ime = os.getenv("ANDROID_ADB_IME_ID", "com.android.adbkeyboard/.AdbIME").strip() or "com.android.adbkeyboard/.AdbIME"
            sogou_ime = os.getenv("ANDROID_SOGOU_IME_ID", "com.sohu.inputmethod.sogou.xiaomi/.SogouIME").strip() or "com.sohu.inputmethod.sogou.xiaomi/.SogouIME"
            self.adb.ime_set(adb_ime)
            time.sleep(self.step_sleep_s)
            self.adb.adbkeyboard_input_text("店小二")
            time.sleep(self.step_sleep_s)
            self.adb.keyevent(66)
            time.sleep(self.step_sleep_s)
            self.adb.ime_set(sogou_ime)
            time.sleep(self.step_sleep_s)
            p4 = self._tap(self.tpl_map_dianxiaoer, threshold=thr_dianxiaoer)

        p5 = self._tap(self.tpl_map_on_the_way, threshold=thr_on_the_way)
        arrival = self.wait_until_arrived_by_coord()
        talk = self.talk_to_dianxiaoer() if arrival.get("arrived") else {"ok": False, "reason": "not_arrived"}

        return {
            "ok": True,
            "map_name": map_name,
            "tap_map_button": p1,
            "tap_search_icon": p2,
            "used_typed_search": used_typed_search,
            "tap_input_icon": p3,
            "tap_dianxiaoer": p4,
            "tap_on_the_way": p5,
            "arrival": arrival,
            "talk": talk,
            "detected": detected,
        }


def main() -> None:
    import shutil
    debug_dir = "debug_capture"
    if os.path.isdir(debug_dir):
        for f in os.listdir(debug_dir):
            fp = os.path.join(debug_dir, f)
            try:
                if os.path.isfile(fp):
                    os.remove(fp)
            except Exception:
                pass
        try:
            shutil.rmtree(debug_dir)
        except Exception:
            pass
    sys_util.load_dotenv()

    bot = AndroidMhxyBot()
    # bot.cleanup_desktop()
    # result = bot.fly_to_hotel()
    # result = bot.enter_hotel()
    result = bot.recieve_baotu_task()

    for k, v in result.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
