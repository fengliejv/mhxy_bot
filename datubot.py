import time
from typing import Any, Dict, Optional, Tuple
from agent_service import extract_baotu_info, route_image_intent

import botconfig
import siliflow_client
import sys_util
from datubot_strategies import select_map_strategy
from image_matcher import match_template
from vision_bot import AndroidVisionBot, _crop_png_bytes, _extract_coord, _parse_roi, wait_until_arrived_by_coord


class Datubot(AndroidVisionBot):

    def detect_current_map(self) -> Dict:
        if not botconfig.MHXY_MAP_ROI:
            raise RuntimeError(f"缺少 {botconfig.KEY_MHXY_MAP_ROI}，请在 .env 配置，例如 0,0,120,120")
        roi = _parse_roi(botconfig.MHXY_MAP_ROI, botconfig.KEY_MHXY_MAP_ROI)
        img_bgr = self.screenshot_bgr()
        png_bytes = _crop_png_bytes(img_bgr, roi)
        sys_util.save_debug_image(img_bgr[roi[1]:roi[3], roi[0]:roi[2]], "android_map_roi_cropped")
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        map_name = str(ocr_result.get("content", "")).strip()
        return {"map_name": map_name, "raw_ocr": ocr_result, "roi": list(roi)}

    def cleanup_desktop(self) -> Dict:
        p_close_guide = self._try_tap(botconfig.ANDROID_TPL_SYSTEM_CLOSE_GUIDE, threshold=botconfig.ANDROID_THR_SYSTEM_CLOSE_GUIDE)
        p_close_task = self._try_tap(botconfig.ANDROID_TPL_SYSTEM_CLOSE_TASK, threshold=botconfig.ANDROID_THR_SYSTEM_CLOSE_TASK)
        p_hide_dialog = self._try_tap(botconfig.ANDROID_TPL_SYSTEM_HIDE_DIALOG, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_DIALOG)
        p_auto_attack_shrink = self._try_tap(
            botconfig.ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK, threshold=botconfig.ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK
        )

        p_expand = self._try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
        p_hide_ui_disable = (
            self._try_tap(botconfig.ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_UI_DISABLE)
            if p_expand is not None
            else None
        )
        p_hide_player_disable = (
            self._try_tap(
                botconfig.ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE
            )
            if p_expand is not None
            else None
        )

        p_back = (
            self._try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
            if p_expand is not None
            else None
        )

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
        matched = self._match_best_of_templates(
            img_bgr, [botconfig.ANDROID_TPL_MAP_BUTTON, botconfig.ANDROID_TPL_MAP_BUTTON_2], threshold=threshold
        )
        if matched is None:
            raise RuntimeError("地图按钮模板匹配失败")
        return self._tap_matched_center(img_bgr, str(matched["template"]), matched["top_left"])

    def talk_to_dianxiaoer(self) -> Dict:
        cleanup = self.cleanup_desktop()
        img_bgr = self.screenshot_bgr()
        matched = self._match_best_of_templates(
            img_bgr,
            [botconfig.ANDROID_TPL_NPC_DIANXIAOER_1, botconfig.ANDROID_TPL_NPC_DIANXIAOER_2, botconfig.ANDROID_TPL_NPC_DIANXIAOER_3],
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
        time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
        return {
            "ok": True,
            "cleanup": cleanup,
            "template": tpl,
            "confidence": conf,
            "tap_edge": (x_edge, y_edge),
            "tap_center": (x_center, y_center),
        }

    def _ocr_text_from_roi_paddle(self, img_bgr, roi: Tuple[int, int, int, int], debug_name: str) -> str:
        png_bytes = _crop_png_bytes(img_bgr, roi)
        sys_util.save_debug_image(img_bgr[roi[1]:roi[3], roi[0]:roi[2]], debug_name)
        ocr_result = siliflow_client.siliconflow_paddleocr(png_bytes)
        return str(ocr_result.get("content", "")).strip()

    def _parse_coord_text(self, text: str) -> Optional[Tuple[int, int]]:
        return _extract_coord(text)

    def detect_coord_by_roi(self) -> Dict:
        if not botconfig.ANDROID_COORD_ROI:
            raise RuntimeError(f"缺少 {botconfig.KEY_ANDROID_COORD_ROI}")
        roi = _parse_roi(botconfig.ANDROID_COORD_ROI, botconfig.KEY_ANDROID_COORD_ROI)
        img_bgr = self.screenshot_bgr()
        text = self._ocr_text_from_roi_paddle(img_bgr, roi, debug_name="android_coord_roi_cropped")
        coord = self._parse_coord_text(text)
        return {"coord": coord, "raw_text": text, "engine": "paddle", "roi": list(roi)}

    def fly_to_hotel(self) -> Dict:
        p_menu_daoju = self._tap(botconfig.ANDROID_TPL_MENU_DAOJU, threshold=botconfig.ANDROID_THR_MENU_DAOJU)
        p_changan_flag = self._tap(botconfig.ANDROID_TPL_PROP_CHANGAN_FLAG, threshold=botconfig.ANDROID_THR_PROP_CHANGAN_FLAG)
        p_use = self._tap(botconfig.ANDROID_TPL_PROP_USE, threshold=botconfig.ANDROID_THR_PROP_USE)

        target_x = botconfig.ANDROID_TELEPORT_TARGET_X
        target_y = botconfig.ANDROID_TELEPORT_TARGET_Y

        img_bgr = self.screenshot_bgr()
        ok, _, locations = match_template(
            img_bgr,
            botconfig.ANDROID_TPL_MAP_TELEPORT_POINT,
            threshold=botconfig.ANDROID_THR_MAP_TELEPORT_POINT,
            find_all=True,
        )
        if not ok or not locations:
            return {
                "ok": False,
                "reason": "teleport_point_not_found",
                "tap_menu_daoju": p_menu_daoju,
                "tap_changan_flag": p_changan_flag,
                "tap_use": p_use,
            }

        tpl_w, tpl_h = self._get_template_wh(botconfig.ANDROID_TPL_MAP_TELEPORT_POINT)
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

        tap_teleport = self._tap_matched_center(img_bgr, botconfig.ANDROID_TPL_MAP_TELEPORT_POINT, best["top_left"])
        time.sleep(botconfig.ANDROID_STEP_SLEEP_S)

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

    def receive_baotu_task(self) -> Dict:
        max_retry = 10

        tap_center = self._tap_screen_center(sleep_after=1.5)

        for i in range(1, max_retry + 1):
            step = self.click_xiaoer()
            img_bgr = self.screenshot_bgr()
            #todo 出来的不一定是婷婷无妨，也可能是反脚本检测
            best_task = self._match_once(
                img_bgr, botconfig.ANDROID_TPL_BAOTU_RECEIVE_TASK, threshold=botconfig.ANDROID_THR_BAOTU_RECEIVE_TASK
            )
            if best_task is not None:
                (top_left, conf) = best_task
                p_task = self._tap_template(
                    img_bgr, botconfig.ANDROID_TPL_BAOTU_RECEIVE_TASK, threshold=botconfig.ANDROID_THR_BAOTU_RECEIVE_TASK
                )
                return {
                    "ok": True
                }

        raise RuntimeError(f"领取宝图任务失败，重试超过{max_retry}次")

    def click_xiaoer(self) -> Dict:
        step_1 = self.go_to_xiaoer(tap_top_right=True)
        wait_until_arrived_by_coord()
        step_2 = self.go_to_xiaoer(tap_top_right=False)
        return {"ok": bool(step_1.get("ok")) and bool(step_2.get("ok")), "step_1": step_1, "sleep_s": 0.5, "step_2": step_2}

    def go_to_xiaoer(self, tap_top_right: bool = False) -> Dict:
        p_expand = self._try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)

        img_bgr = self.screenshot_bgr()
        matched = self._match_first_of_templates(
            img_bgr,
            [botconfig.ANDROID_TPL_NPC_DIANXIAOER_1, botconfig.ANDROID_TPL_NPC_DIANXIAOER_2, botconfig.ANDROID_TPL_NPC_DIANXIAOER_3],
            threshold=botconfig.ANDROID_THR_NPC_XIAOER,
        )
        if matched is None:
            self._try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
            return {"ok": False, "reason": "npc_not_found", "tap_expand": p_expand}

        tpl = str(matched["template"])
        top_left = matched["top_left"]
        conf = float(matched["confidence"])
        if tap_top_right:
            w, h = self._get_template_wh(tpl)
            margin = max(5, int(min(w, h) * 0.15))
            margin = min(margin, max(1, w - 1), max(1, h - 1))
            x = int(top_left[0] + w - margin)
            y = int(top_left[1] + margin)
            self.adb.tap(x + 10, y + 10)
        else:
            self._tap_matched_center(img_bgr, tpl, top_left)
        p_back = self._try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)

        return {
            "ok": True
        }

    def enter_hotel(self) -> Dict:
        p_expand = self._tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
        p_hotel_door = self._tap(botconfig.ANDROID_TPL_CHANGAN_HOTEL_DOOR, threshold=botconfig.ANDROID_THR_CHANGAN_HOTEL_DOOR)
        p_back = self._tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
        return {"ok": True, "tap_expand": p_expand, "tap_hotel_door": p_hotel_door, "tap_back": p_back}

    def _prepare_receive_baotu_task(self) -> None:
        cleanup = self.cleanup_desktop()
        fly = self.fly_to_hotel()
        enter = self.enter_hotel()

    def _judge_after_receive(self) -> Dict[str, Any]:
        time.sleep(max(0.5, float(botconfig.ANDROID_STEP_SLEEP_S)))
        img_bgr = self.screenshot_bgr()
        judged = route_image_intent(img_bgr)
        return {"judged": judged}

    def _got_baotu_task(self, judged: Dict[str, Any]) -> bool:
        return str(judged.get("category", "")).strip().lower() in ("mhxy_baotu", "baotu", "mhxy")

    def _build_qiangdao_plan_after_got_baotu(self) -> Dict[str, Any]:
        tap_center = self._tap_screen_center()
        extracted = self._capture_and_extract_baotu_llm()
        llm_qiangdao_name = extracted["llm_qiangdao_name"]
        llm_map_name = extracted["llm_map_name"]
        llm_coord = extracted["llm_coord"]
        strategy = select_map_strategy(llm_map_name)
        qiangdao_plan = strategy.execute(self, destination=llm_map_name, coord=llm_coord)
        return {
            "tap_center_after_got_baotu": tap_center,
            "llm_qiangdao_name": llm_qiangdao_name,
            "llm_map_name": llm_map_name,
            "llm_coord": llm_coord,
            "qiangdao_plan": qiangdao_plan,
        }

    def _try_receive_and_judge_baotu_once(self, attempt: int) -> Dict[str, Any]:
        try:
            receive = self.receive_baotu_task()
        except Exception as e:
            return {"attempt": attempt, "receive_error": str(e)}

        try:
            judged = self._judge_after_receive()["judged"]
        except Exception as e:
            judged = {"category": "other", "error": str(e)}

        got_baotu = self._got_baotu_task(judged)
        return {"attempt": attempt, "receive": receive, "judge": judged, "got_baotu": got_baotu}

    def excutedatu(self) -> None:
        self._prepare_receive_baotu_task()
        attempts = []
        llm_map_name = ""
        for i in range(1, 4):
            attempt_result = self._try_receive_and_judge_baotu_once(i)
            attempts.append(attempt_result)

            if not bool(attempt_result.get("got_baotu")):
                continue

            plan = self._build_qiangdao_plan_after_got_baotu()
            llm_map_name = str(plan.get("llm_map_name", "") or "").strip()


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
