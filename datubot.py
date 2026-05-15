import re
import time
from typing import Any, Dict, Optional, Tuple
from agent_service import extract_baotu_info

import cv2
import numpy as np

import botconfig
import siliflow_client
import sys_util
from vision_bot import AndroidVisionBot


def _parse_roi(roi_text: str, env_name: str) -> Tuple[int, int, int, int]:
    parts = [x.strip() for x in str(roi_text or "").split(",")]
    if len(parts) != 4:
        raise RuntimeError(f"{env_name} 格式错误，期望 x1,y1,x2,y2")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError(f"{env_name} 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError(f"{env_name} 数值无效，要求 x2>x1,y2>y1")
    return x1, y1, x2, y2


def _crop_png_bytes(img_bgr: np.ndarray, roi: Tuple[int, int, int, int]) -> bytes:
    x1, y1, x2, y2 = roi
    cropped = img_bgr[y1:y2, x1:x2]
    ok, buf = cv2.imencode(".png", cropped)
    if not ok:
        raise RuntimeError("PNG 编码失败")
    return bytes(buf)


def _extract_coord(text: str) -> Optional[Tuple[int, int]]:
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


def _extract_destination(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    candidates = [
        "建业城",
        "长寿村",
        "朱紫国",
        "傲来国",
        "宝象国",
        "长安郊外",
        "东海湾",
        "长安城",
        "长安酒馆",
    ]
    for name in candidates:
        if name in s:
            return name
    return s


class LocationStrategy:
    name = "unknown"

    def execute(self, bot: "Datubot", destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return {"ok": False, "reason": "not_implemented", "strategy": self.name, "destination": destination, "coord": coord}
    
class Location_with_fly(LocationStrategy):
    name = "fly"

    def execute(self, bot: "Datubot", destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        dest = str(destination or "").strip()
        if not dest:
            return {"ok": False, "reason": "empty_destination", "strategy": self.name, "destination": destination, "coord": coord}
        map_tpl_by_dest = {
            "傲来国": "assets/android/map/feixingfuditu/aolaiguo.png",
            "宝象国": "assets/android/map/feixingfuditu/baoxiangguo.png",
            "长安城": "assets/android/map/feixingfuditu/changancheng.png",
            "长寿村": "assets/android/map/feixingfuditu/changshoucun.png",
            "建邺城": "assets/android/map/feixingfuditu/jianye.png",
            "朱紫国": "assets/android/map/feixingfuditu/zhuziguo.png",
            "西梁女国": "assets/android/map/feixingfuditu/xilaingnvguo.png",
        }
        map_tpl = map_tpl_by_dest.get(dest)
        if not map_tpl:
            return {"ok": False, "reason": "unsupported_destination", "strategy": self.name, "destination": destination, "coord": coord}

        thr_menu_daoju = botconfig.env_float("ANDROID_THR_MENU_DAOJU", float(bot.match_threshold))
        thr_feixingfu = botconfig.env_float("ANDROID_THR_PROP_FEIXINGFU", float(bot.match_threshold))
        thr_use = botconfig.env_float("ANDROID_THR_PROP_USE", float(bot.match_threshold))
        thr_map = botconfig.env_float("ANDROID_THR_FEIXINGFU_MAP", float(bot.match_threshold))
        thr_close = botconfig.env_float("ANDROID_THR_DAOJU_CLOSE", float(bot.match_threshold))

        tpl_feixingfu = "assets/android/daoju/feixingfu.png"
        tpl_use = "assets/android/daoju/jiemian/shiyong.png"
        tpl_close_bag = "assets/android/daoju/jiemian/guanbi.png"

        tap_menu = bot._tap(bot.tpl_menu_daoju, threshold=thr_menu_daoju)
        tap_feixingfu = bot._tap(tpl_feixingfu, threshold=thr_feixingfu)
        tap_use = bot._tap(tpl_use, threshold=thr_use)
        tap_map = bot._tap(map_tpl, threshold=thr_map)
        tap_close = bot._try_tap(tpl_close_bag, threshold=thr_close)
        return {
            "ok": True,
            "strategy": self.name,
            "destination": destination,
            "coord": coord,
            "map_template": map_tpl,
            "tap_menu_daoju": tap_menu,
            "tap_feixingfu": tap_feixingfu,
            "tap_use": tap_use,
            "tap_map": tap_map,
            "tap_close_bag": tap_close,
        }

class Location_shituo(Location_with_fly):
    name = "shituo"

    def execute(self, bot: "Datubot", destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        from vision_bot import navigate_to_coord

        fly = super().execute(bot, destination="朱紫国", coord=None)
        if not bool(fly.get("ok")):
            return {"ok": False, "reason": "fly_to_zhuziguo_failed", "strategy": self.name, "fly": fly}

        nav = navigate_to_coord(bot.adb, x=7, y=4)
        arrival = nav.get("arrival")

        thr_transfer = botconfig.env_float("ANDROID_THR_SYSTEM_TRANSFER", float(bot.match_threshold))
        max_retry = botconfig.env_int("ANDROID_TRANSFER_RETRY", 10)
        retry_sleep_s = botconfig.env_float("ANDROID_TRANSFER_RETRY_SLEEP_S", float(bot.step_sleep_s))
        tpl_transfer = r"assets\android\system\transfer.jpg"
        tap_transfer = None
        for _ in range(max(1, max_retry)):
            tap_transfer = bot._try_tap(tpl_transfer, threshold=thr_transfer)
            if tap_transfer is not None:
                break
            time.sleep(max(0.1, retry_sleep_s))

        if tap_transfer is None:
            return {"ok": False, "reason": "transfer_not_found", "strategy": self.name, "fly": fly, "navigate": nav, "arrival": arrival}

        time.sleep(max(0.5, float(bot.step_sleep_s)))
        detected_after = bot.detect_current_map()
        return {
            "ok": True,
            "strategy": self.name,
            "fly_to_zhuziguo": fly,
            "navigate_to_7_4": nav,
            "arrival": arrival,
            "tap_transfer": tap_transfer,
            "detected_after_transfer": detected_after,
        }


class QiangdaoStrategyB(LocationStrategy):
    name = "B"

    def execute(self, bot: "Datubot", destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return {"ok": False, "reason": "not_implemented", "strategy": self.name, "destination": destination, "coord": coord}


class QiangdaoStrategyC(LocationStrategy):
    name = "C"

    def execute(self, bot: "Datubot", destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return {"ok": False, "reason": "not_implemented", "strategy": self.name, "destination": destination, "coord": coord}





def _select_map_strategy(map_name: str) -> LocationStrategy:
    dest = str(map_name or "").strip()
    if dest in ("建邺城", "长寿村", "朱紫国", "傲来国", "宝象国","女儿村","西梁女国"):
        return QiangdaoStrategyA()
    if dest in ("江南野外",):
        return QiangdaoStrategyB()
    if dest in ("狮驼岭",):
        return QiangdaoStrategyC()
    if dest in ("东海湾",):
        return QiangdaoStrategyC()
    if dest in ("大唐国境",):
        return QiangdaoStrategyC()
    if dest in ("花果山",):
        return QiangdaoStrategyC()
    if dest in ("长寿郊外",):
        return QiangdaoStrategyC()
    if dest in ("化生寺",):
        return QiangdaoStrategyC()
    if dest in ("东海湾",):
        return QiangdaoStrategyC()
    if dest in ("阴曹地府",):
        return QiangdaoStrategyC()
    if dest in ("普陀山",):
        return QiangdaoStrategyC()
    if dest in ("狮驼岭",):
        return QiangdaoStrategyC()
    if dest in ("五庄观",):
        return QiangdaoStrategyC()

    return LocationStrategy()


class Datubot(AndroidVisionBot):

    def __init__(self, adb=None) -> None:
        super().__init__(adb=adb)
        self.map_roi_text = botconfig.env_str("MHXY_MAP_ROI", "")
        self.coord_roi_text = botconfig.env_str("ANDROID_COORD_ROI", "")

        self.tpl_map_button = botconfig.env_str("ANDROID_TPL_MAP_BUTTON", "assets/android/map/map_button.jpg")
        self.tpl_map_button_2 = botconfig.env_str("ANDROID_TPL_MAP_BUTTON_2", "assets/android/map/map_button2.png")
        self.tpl_map_search_icon = botconfig.env_str("ANDROID_TPL_MAP_SEARCH_ICON", "assets/android/map/map_search_icon.png")
        self.tpl_map_input_icon = botconfig.env_str("ANDROID_TPL_MAP_INPUT_ICON", "assets/android/map/map_input_icon.png")
        self.tpl_map_go = botconfig.env_str("ANDROID_TPL_MAP_GO", "assets/android/map/map_go.jpg")
        self.tpl_map_exit = botconfig.env_str("ANDROID_TPL_MAP_EXIT", "assets/android/map/map_exit.jpg")
        self.tpl_map_dianxiaoer = botconfig.env_str("ANDROID_TPL_MAP_DIANXIAOER", "assets/android/map/map_dianxiaoer.png")
        self.tpl_map_on_the_way = botconfig.env_str("ANDROID_TPL_MAP_ON_THE_WAY", "assets/android/map/map_on_the_way.png")
        self.tpl_menu_daoju = botconfig.env_str("ANDROID_TPL_MENU_DAOJU", "assets/android/memu/daoju.jpg")
        self.tpl_prop_changan_flag = botconfig.env_str("ANDROID_TPL_PROP_CHANGAN_FLAG", "assets/android/daoju/changandaobiaoqi.png")
        self.tpl_prop_use = botconfig.env_str("ANDROID_TPL_PROP_USE", "assets/android/daoju/jiemian/shiyong.png")
        self.tpl_map_teleport_point = botconfig.env_str("ANDROID_TPL_MAP_TELEPORT_POINT", "assets/android/map/daobiaoqiditu/chuansongdian.png")
        self.tpl_baotu_receive_task = botconfig.env_str("ANDROID_TPL_BAOTU_RECEIVE_TASK", "assets/android/baotu/tingtingwufang.png")
        self.tpl_changan_hotel_door = botconfig.env_str("ANDROID_TPL_CHANGAN_HOTEL_DOOR", "assets/android/changancheng/jiudianmenkou.png")
        self.tpl_system_close_guide = botconfig.env_str("ANDROID_TPL_SYSTEM_CLOSE_GUIDE", "assets/android/system/guanbizhiyin.png")
        self.tpl_system_close_task = botconfig.env_str("ANDROID_TPL_SYSTEM_CLOSE_TASK", "assets/android/system/close_task.jpg")
        self.tpl_system_hide_dialog = botconfig.env_str("ANDROID_TPL_SYSTEM_HIDE_DIALOG", "assets/android/system/yincangduihua.png")
        self.tpl_system_auto_attack_shrink = botconfig.env_str("ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK", "assets/android/system/zidonggongjisuoxiao.png")
        self.tpl_system_expand = botconfig.env_str("ANDROID_TPL_SYSTEM_EXPAND", "assets/android/system/expand.jpg")
        self.tpl_system_hide_ui_disable = botconfig.env_str("ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE", "assets/android/system/yincangjiemian_disable.png")
        self.tpl_system_hide_player_disable = botconfig.env_str("ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE", "assets/android/system/yincangwanjia_disable.png")
        self.tpl_system_back = botconfig.env_str("ANDROID_TPL_SYSTEM_BACK", "assets/android/system/back.png")
        self.tpl_npc_dianxiaoer_1 = botconfig.env_str("ANDROID_TPL_NPC_DIANXIAOER_1", "assets/android/npc/dianxiaoer1.png")
        self.tpl_npc_dianxiaoer_2 = botconfig.env_str("ANDROID_TPL_NPC_DIANXIAOER_2", "assets/android/npc/dianxiaoer2.png")
        self.tpl_npc_dianxiaoer_3 = botconfig.env_str("ANDROID_TPL_NPC_DIANXIAOER_3", "assets/android/npc/dianxiaoer3.png")

    def detect_current_map(self) -> Dict:
        if not self.map_roi_text:
            raise RuntimeError("缺少 MHXY_MAP_ROI，请在 .env 配置，例如 0,0,120,120")
        roi = _parse_roi(self.map_roi_text, "MHXY_MAP_ROI")
        img_bgr = self.screenshot_bgr()
        png_bytes = _crop_png_bytes(img_bgr, roi)
        sys_util.save_debug_image(img_bgr[roi[1]:roi[3], roi[0]:roi[2]], "android_map_roi_cropped")
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        map_name = str(ocr_result.get("content", "")).strip()
        return {"map_name": map_name, "raw_ocr": ocr_result, "roi": list(roi)}

    def cleanup_desktop(self) -> Dict:
        thr_close_guide = botconfig.env_float("ANDROID_THR_SYSTEM_CLOSE_GUIDE", float(self.match_threshold))
        thr_close_task = botconfig.env_float("ANDROID_THR_SYSTEM_CLOSE_TASK", float(self.match_threshold))
        thr_hide_dialog = botconfig.env_float("ANDROID_THR_SYSTEM_HIDE_DIALOG", float(self.match_threshold))
        thr_auto_attack_shrink = botconfig.env_float("ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK", float(self.match_threshold))
        thr_expand = botconfig.env_float("ANDROID_THR_SYSTEM_EXPAND", float(self.match_threshold))
        thr_hide_ui_disable = botconfig.env_float("ANDROID_THR_SYSTEM_HIDE_UI_DISABLE", float(self.match_threshold))
        thr_hide_player_disable = botconfig.env_float("ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE", float(self.match_threshold))
        thr_back = botconfig.env_float("ANDROID_THR_SYSTEM_BACK", float(self.match_threshold))

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

    def _tap_screen_center(self, sleep_after: float = 0.0) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        h, w = img_bgr.shape[:2]
        x = int(w / 2)
        y = int(h / 2)
        self.adb.tap(x, y)
        if float(sleep_after) > 0:
            time.sleep(float(sleep_after))
        return x, y

    def _capture_and_extract_baotu_llm(self) -> Dict[str, Any]:
        img_bgr = self.screenshot_bgr()
        llm_baotu_info = extract_baotu_info(img_bgr)
        llm_parsed = llm_baotu_info.get("parsed") if isinstance(llm_baotu_info, dict) else None
        llm_qiangdao_name = ""
        llm_map_name = ""
        llm_coord = None
        if isinstance(llm_parsed, dict):
            llm_qiangdao_name = str(llm_parsed.get("qiangdao_name", "") or "").strip()
            llm_map_name = str(llm_parsed.get("map_name", "") or "").strip()
            coord_list = llm_parsed.get("coord")
            if isinstance(coord_list, (list, tuple)) and len(coord_list) >= 2:
                try:
                    llm_coord = (int(coord_list[0]), int(coord_list[1]))
                except Exception:
                    llm_coord = None
        return {
            "llm_baotu_info": llm_baotu_info,
            "llm_parsed": llm_parsed,
            "llm_qiangdao_name": llm_qiangdao_name,
            "llm_map_name": llm_map_name,
            "llm_coord": llm_coord,
        }

    def tap_map_button(self, threshold: float = 0.6) -> Tuple[int, int]:
        img_bgr = self.screenshot_bgr()
        matched = self._match_best_of_templates(img_bgr, [self.tpl_map_button, self.tpl_map_button_2], threshold=threshold)
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

    def _ocr_text_from_roi_paddle(self, img_bgr: np.ndarray, roi: Tuple[int, int, int, int], debug_name: str) -> str:
        png_bytes = _crop_png_bytes(img_bgr, roi)
        sys_util.save_debug_image(img_bgr[roi[1]:roi[3], roi[0]:roi[2]], debug_name)
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        return str(ocr_result.get("content", "")).strip()

    def _parse_coord_text(self, text: str) -> Optional[Tuple[int, int]]:
        return _extract_coord(text)

    def detect_coord_by_roi(self) -> Dict:
        if not self.coord_roi_text:
            raise RuntimeError("缺少 ANDROID_COORD_ROI")
        roi = _parse_roi(self.coord_roi_text, "ANDROID_COORD_ROI")
        img_bgr = self.screenshot_bgr()
        text = self._ocr_text_from_roi_paddle(img_bgr, roi, debug_name="android_coord_roi_cropped")
        coord = self._parse_coord_text(text)
        return {"coord": coord, "raw_text": text, "engine": "paddle", "roi": list(roi)}

    def wait_until_arrived_by_coord(self) -> Dict:
        max_wait_s = botconfig.env_float("ANDROID_ARRIVAL_MAX_WAIT_S", 60.0)
        interval_s = botconfig.env_float("ANDROID_ARRIVAL_CHECK_INTERVAL_S", 1.0)
        stable_need = botconfig.env_int("ANDROID_ARRIVAL_STABLE_COUNT", 2)
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
        from image_matcher import match_template

        thr_menu_daoju = botconfig.env_float("ANDROID_THR_MENU_DAOJU", float(self.match_threshold))
        thr_prop_changan_flag = botconfig.env_float("ANDROID_THR_PROP_CHANGAN_FLAG", float(self.match_threshold))
        thr_prop_use = botconfig.env_float("ANDROID_THR_PROP_USE", float(self.match_threshold))
        thr_teleport_point = botconfig.env_float("ANDROID_THR_MAP_TELEPORT_POINT", float(self.match_threshold))

        p_menu_daoju = self._tap(self.tpl_menu_daoju, threshold=thr_menu_daoju)
        p_changan_flag = self._tap(self.tpl_prop_changan_flag, threshold=thr_prop_changan_flag)
        p_use = self._tap(self.tpl_prop_use, threshold=thr_prop_use)

        target_x = botconfig.env_int("ANDROID_TELEPORT_TARGET_X", 1640)
        target_y = botconfig.env_int("ANDROID_TELEPORT_TARGET_Y", 500)

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

        tpl_w, tpl_h = self._get_template_wh(self.tpl_map_teleport_point)
        best = None
        for (top_left, conf) in locations:
            cx = int(top_left[0] + tpl_w / 2)
            cy = int(top_left[1] + tpl_h / 2)
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
        thr_receive_task = botconfig.env_float("ANDROID_THR_BAOTU_RECEIVE_TASK", float(self.match_threshold))
        attempts = []

        tap_center = self._tap_screen_center(sleep_after=1.5)

        for i in range(1, max_retry + 1):
            step = self.click_xiaoer()
            img_bgr = self.screenshot_bgr()
            best_task = self._match_once(img_bgr, self.tpl_baotu_receive_task, threshold=thr_receive_task)
            if best_task is not None:
                (top_left, conf) = best_task
                p_task = self._tap_template(img_bgr, self.tpl_baotu_receive_task, threshold=thr_receive_task)
                return {
                    "ok": True,
                    "attempt": i,
                    "tap_center_before_loop": tap_center,
                    "step": step,
                    "receive_task": {"template": self.tpl_baotu_receive_task, "top_left": top_left, "confidence": float(conf), "tap": p_task},
                }
            attempts.append({"attempt": i, "step": step, "receive_task": None})

        raise RuntimeError(f"领取宝图任务失败，重试超过{max_retry}次: {attempts}")

    def click_xiaoer(self) -> Dict:
        step_1 = self.go_to_xiaoer(tap_top_right=True)
        time.sleep(1)
        step_2 = self.go_to_xiaoer(tap_top_right=False)
        return {"ok": bool(step_1.get("ok")) and bool(step_2.get("ok")), "step_1": step_1, "sleep_s": 0.5, "step_2": step_2}

    def go_to_xiaoer(self, tap_top_right: bool = False) -> Dict:
        thr_expand = botconfig.env_float("ANDROID_THR_SYSTEM_EXPAND", float(self.match_threshold))
        thr_xiaoer = botconfig.env_float("ANDROID_THR_NPC_XIAOER", 0.4)
        thr_back = botconfig.env_float("ANDROID_THR_SYSTEM_BACK", float(self.match_threshold))

        p_expand = self._try_tap(self.tpl_system_expand, threshold=thr_expand)

        img_bgr = self.screenshot_bgr()
        matched = self._match_first_of_templates(img_bgr, [self.tpl_npc_dianxiaoer_1, self.tpl_npc_dianxiaoer_2, self.tpl_npc_dianxiaoer_3], threshold=thr_xiaoer)
        if matched is None:
            self._try_tap(self.tpl_system_back, threshold=thr_back)
            return {"ok": False, "reason": "npc_not_found", "tap_expand": p_expand}

        tpl = str(matched["template"])
        top_left = matched["top_left"]
        conf = float(matched["confidence"])
        tap_center = None
        tap_top_right_pt = None
        if tap_top_right:
            w, h = self._get_template_wh(tpl)
            margin = max(5, int(min(w, h) * 0.15))
            margin = min(margin, max(1, w - 1), max(1, h - 1))
            x = int(top_left[0] + w - margin)
            y = int(top_left[1] + margin)
            self.adb.tap(x + 10, y + 10)
            tap_top_right_pt = (x, y)
        else:
            tap_center = self._tap_matched_center(img_bgr, tpl, top_left)
        p_back = self._try_tap(self.tpl_system_back, threshold=thr_back)
        # time.sleep(self.step_sleep_s)

        return {
            "ok": True,
            "tap_expand": p_expand,
            "template": tpl,
            "confidence": conf,
            "top_left": top_left,
            "tap_pos": "top_right" if tap_top_right else "center",
            "tap_center": tap_center,
            "tap_top_right": tap_top_right_pt,
            "tap_back": p_back,
        }

    def enter_hotel(self) -> Dict:
        thr_expand = botconfig.env_float("ANDROID_THR_SYSTEM_EXPAND", float(self.match_threshold))
        thr_hotel_door = botconfig.env_float("ANDROID_THR_CHANGAN_HOTEL_DOOR", float(self.match_threshold))
        thr_back = botconfig.env_float("ANDROID_THR_SYSTEM_BACK", float(self.match_threshold))

        p_expand = self._tap(self.tpl_system_expand, threshold=thr_expand)
        p_hotel_door = self._tap(self.tpl_changan_hotel_door, threshold=thr_hotel_door)
        p_back = self._tap(self.tpl_system_back, threshold=thr_back)
        return {"ok": True, "tap_expand": p_expand, "tap_hotel_door": p_hotel_door, "tap_back": p_back}

    def excutedatu(self) -> Dict:
        self.cleanup_desktop()
        detected = self.detect_current_map()
        fly = self.fly_to_hotel()
        enter = self.enter_hotel()
        attempts = []
        for i in range(1, 4):
            receive = None
            try:
                receive = self.recieve_baotu_task()
            except Exception as e:
                attempts.append({"attempt": i, "receive_error": str(e)})
                continue

            time.sleep(max(0.5, float(self.step_sleep_s)))
            img_bgr = self.screenshot_bgr()
            try:
                from agent_service import route_image_intent
                judged = route_image_intent(img_bgr)
            except Exception as e:
                judged = {"category": "other", "error": str(e)}

            got_baotu = str(judged.get("category", "")).strip().lower() in ("mhxy_baotu", "baotu", "mhxy")
            attempts.append({"attempt": i, "receive": receive, "judge": judged, "got_baotu": got_baotu})
            if got_baotu:
                tap_center = self._tap_screen_center()
                extracted = self._capture_and_extract_baotu_llm()
                llm_qiangdao_name = extracted["llm_qiangdao_name"]
                llm_map_name = extracted["llm_map_name"]
                llm_coord = extracted["llm_coord"]
                strategy = _select_map_strategy(llm_map_name)
                qiangdao_plan = strategy.execute(self, destination=llm_map_name, coord=llm_coord)
                return {
                    "ok": True,
                    "branch": "fly_enter_receive",
                    "map_name": llm_map_name,
                    "detected": detected,
                    "fly_to_hotel": fly,
                    "enter_hotel": enter,
                    "tap_center_after_got_baotu": tap_center,
                    "llm_qiangdao_name": llm_qiangdao_name,
                    "llm_map_name": llm_map_name,
                    "llm_coord": llm_coord,
                    "qiangdao_plan": qiangdao_plan,
                }

        return {
            "ok": False,
            "reason": "baotu_task_not_detected_after_receive",
            "branch": "fly_enter_receive",
            "map_name": llm_map_name,
            "detected": detected,
            "fly_to_hotel": fly,
            "enter_hotel": enter,
            "attempts": attempts,
        }


def main() -> None:
    # bot = Datubot()
    # result = bot.excutedatu()
    # for k, v in result.items():
    #     print(f"{k}: {v}")
    sys_util.clear_debug_capture()
    botconfig.init()
    bot = Datubot()
    
    extracted = bot._capture_and_extract_baotu_llm()
    llm_baotu_info = extracted["llm_baotu_info"]
    llm_qiangdao_name = extracted["llm_qiangdao_name"]
    llm_map_name = extracted["llm_map_name"]
    llm_coord = extracted["llm_coord"]  
    print(extracted)  
    # bot.cleanup_desktop()
    # detected = bot.detect_current_map()
    # fly = bot.fly_to_hotel()
    # enter = bot.enter_hotel()

    # for k, v in result.items():
    #     print(f"{k}: {v}")


if __name__ == "__main__":
    main()
