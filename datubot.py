import time
from typing import Any, Dict, Optional, Tuple

import botconfig
import adb_util
import siliflow_client
import sys_util
import vision_bot
import route_strategies as datubot_strategies
from agent_service import extract_baotu_info, route_image_intent
from image_matcher import match_template


def cleanup_desktop() -> Dict[str, Any]:
    p_close_guide = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_CLOSE_GUIDE, threshold=botconfig.ANDROID_THR_SYSTEM_CLOSE_GUIDE)
    p_close_task = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_CLOSE_TASK, threshold=botconfig.ANDROID_THR_SYSTEM_CLOSE_TASK)
    p_hide_dialog = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_HIDE_DIALOG, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_DIALOG)
    p_auto_attack_shrink = vision_bot.try_tap(
        botconfig.ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK, threshold=botconfig.ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK
    )

    p_expand = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
    p_hide_ui_disable = (
        vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_UI_DISABLE)
        if p_expand is not None
        else None
    )
    p_hide_player_disable = (
        vision_bot.try_tap(
            botconfig.ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE
        )
        if p_expand is not None
        else None
    )

    p_back = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK) if p_expand is not None else None
    p_map_button = vision_bot.try_tap_best(
        [botconfig.ANDROID_TPL_MAP_BUTTON, botconfig.ANDROID_TPL_MAP_BUTTON_2],
        threshold=botconfig.ANDROID_THR_MAP_BUTTON,
    )
    p_map_exit = (
        vision_bot.try_tap(botconfig.ANDROID_TPL_MAP_EXIT, threshold=botconfig.ANDROID_MATCH_THRESHOLD)
        if p_map_button is not None
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
        "tap_map_button": p_map_button,
        "tap_map_exit": p_map_exit,
    }


def talk_to_dianxiaoer() -> Dict[str, Any]:
    cleanup = cleanup_desktop()
    img_bgr = vision_bot.screenshot_bgr()
    matched = vision_bot.match_best_of_templates(
        img_bgr,
        [botconfig.ANDROID_TPL_NPC_DIANXIAOER_1, botconfig.ANDROID_TPL_NPC_DIANXIAOER_2, botconfig.ANDROID_TPL_NPC_DIANXIAOER_3],
        threshold=0.5,
    )
    if matched is None:
        return {"ok": False, "reason": "npc_not_found", "cleanup": cleanup}

    tpl = str(matched["template"])
    top_left = matched["top_left"]
    conf = float(matched["confidence"])
    w, h = vision_bot.get_template_wh(tpl)
    margin = max(5, int(w * 0.1))
    margin = min(margin, max(1, w - 1))
    x_edge = int(top_left[0] + margin)
    y_edge = int(top_left[1] + h / 2)
    x_center = int(top_left[0] + w / 2)
    y_center = int(top_left[1] + h / 2)

    adb_util.tap(x_edge, y_edge)
    time.sleep(2.0)
    adb_util.tap(x_center, y_center)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    return {
        "ok": True,
        "cleanup": cleanup,
        "template": tpl,
        "confidence": conf,
        "tap_edge": (x_edge, y_edge),
        "tap_center": (x_center, y_center),
    }


def fly_to_hotel() -> Dict[str, Any]:
    p_menu_daoju = vision_bot.tap_template(botconfig.ANDROID_TPL_MENU_DAOJU, threshold=botconfig.ANDROID_THR_MENU_DAOJU)
    p_changan_flag = vision_bot.tap_template(botconfig.ANDROID_TPL_PROP_CHANGAN_FLAG, threshold=botconfig.ANDROID_THR_PROP_CHANGAN_FLAG)
    p_use = vision_bot.tap_template(botconfig.ANDROID_TPL_PROP_USE, threshold=botconfig.ANDROID_THR_PROP_USE)

    target_x = botconfig.ANDROID_TELEPORT_TARGET_X
    target_y = botconfig.ANDROID_TELEPORT_TARGET_Y

    img_bgr = vision_bot.screenshot_bgr()
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

    tpl_w, tpl_h = vision_bot.get_template_wh(botconfig.ANDROID_TPL_MAP_TELEPORT_POINT)
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

    adb_util.tap(best["center"][0], best["center"][1])
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)

    return {
        "ok": True,
        "tap_menu_daoju": p_menu_daoju,
        "tap_changan_flag": p_changan_flag,
        "tap_use": p_use,
        "target": (target_x, target_y),
        "teleport_point_best": best,
        "tap_teleport": tuple(best["center"]),
        "teleport_point_count": int(len(locations)),
    }


def go_to_xiaoer(tap_top_right: bool = False) -> Dict[str, Any]:
    p_expand = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)

    img_bgr = vision_bot.screenshot_bgr()
    matched = vision_bot.match_first_of_templates(
        img_bgr,
        [botconfig.ANDROID_TPL_NPC_DIANXIAOER_1, botconfig.ANDROID_TPL_NPC_DIANXIAOER_2, botconfig.ANDROID_TPL_NPC_DIANXIAOER_3],
        threshold=botconfig.ANDROID_THR_NPC_XIAOER,
    )
    if matched is None:
        vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
        return {"ok": False, "reason": "npc_not_found", "tap_expand": p_expand}

    tpl = str(matched["template"])
    top_left = matched["top_left"]
    conf = float(matched["confidence"])
    w, h = vision_bot.get_template_wh(tpl)

    tap_center = None
    tap_top_right_pt = None
    if tap_top_right:
        margin = max(5, int(min(w, h) * 0.15))
        margin = min(margin, max(1, w - 1), max(1, h - 1))
        x = int(top_left[0] + w - margin)
        y = int(top_left[1] + margin)
        adb_util.tap(x + 10, y + 10)
        tap_top_right_pt = (x, y)
    else:
        cx = int(top_left[0] + w / 2)
        cy = int(top_left[1] + h / 2)
        adb_util.tap(cx, cy)
        tap_center = (cx, cy)

    p_back = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)

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


def click_xiaoer() -> None:
    # step_1 = go_to_xiaoer(tap_top_right=True)
    # vision_bot.wait_until_arrived_by_coord()
    go_to_xiaoer(tap_top_right=False)




def enter_hotel() -> Dict[str, Any]:
    p_expand = vision_bot.tap_template(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
    p_hotel_door = vision_bot.tap_template(botconfig.ANDROID_TPL_CHANGAN_HOTEL_DOOR, threshold=botconfig.ANDROID_THR_CHANGAN_HOTEL_DOOR)
    p_back = vision_bot.tap_template(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
    return {"ok": True, "tap_expand": p_expand, "tap_hotel_door": p_hotel_door, "tap_back": p_back}


def receive_baotu_task() -> Dict[str, Any]:
    max_retry = 5
    attempts = []
    for i in range(1, max_retry + 1):
        close_to_xiaoer()
        click_xiaoer()
        receive_task = vision_bot.try_tap_template(
            template_path=botconfig.ANDROID_TPL_BAOTU_RECEIVE_TASK,
            threshold=botconfig.ANDROID_THR_BAOTU_RECEIVE_TASK,
        )
        if receive_task is None:
            has_daoju = vision_bot.template_exists(
                template_path=botconfig.ANDROID_TPL_MENU_DAOJU,
                threshold=botconfig.ANDROID_MATCH_THRESHOLD,
            )
            random_task = None
            if not has_daoju:
                random_task = route_image_intent(img_bgr)
            attempts.append(
                {
                    "attempt": i,
                    "receive_task": None,
                    "has_daoju_icon": has_daoju,
                    "random_task": random_task,
                }
            )
            continue

        tap_back_after_receive = vision_bot.try_tap(
            botconfig.ANDROID_TPL_SYSTEM_BACK,
            threshold=botconfig.ANDROID_THR_SYSTEM_BACK,
        )
        return {
            "ok": True,
            "attempt": i,
            "tap_center_before_loop": tap_center,
            "step": step,
            "receive_task": receive_task,
            "tap_back_after_receive": tap_back_after_receive,
        }

    raise RuntimeError(f"领取宝图任务失败，重试超过{max_retry}次: {attempts}")

def close_to_xiaoer() -> Dict[str, Any]:
    p_map_button = vision_bot.try_tap_best(
        [botconfig.ANDROID_TPL_MAP_BUTTON, botconfig.ANDROID_TPL_MAP_BUTTON_2],
        threshold=botconfig.ANDROID_THR_MAP_BUTTON,
    )
    if p_map_button is None:
        return {"ok": False, "reason": "map_button_not_found"}

    p_search = vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_SEARCH_ICON,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    p_input = vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_INPUT_ICON,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )

    adb_util.ime_set(botconfig.ANDROID_ADB_IME_ID)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    adb_util.adbkeyboard_input_text("店小二")
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    adb_util.ime_set(botconfig.ANDROID_SOGOU_IME_ID)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)

    p_on_the_way = vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_ON_THE_WAY,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    p_map_exit = vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_EXIT,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    arrival = vision_bot.wait_until_arrived_by_coord()
    return {
        "ok": True,
        "tap_map_button": p_map_button,
        "tap_map_search_icon": p_search,
        "tap_map_input_icon": p_input,
        "input_text": "店小二",
        "tap_on_the_way": p_on_the_way,
        "tap_map_exit": p_map_exit,
        "arrival": arrival,
    }


def capture_and_extract_baotu_llm() -> Dict[str, Any]:
    img_bgr = vision_bot.screenshot_bgr()
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


def prepare_receive_baotu_task() -> Dict[str, Any]:
    cleanup = cleanup_desktop()
    fly = fly_to_hotel()
    enter = enter_hotel()
    return {"cleanup": cleanup, "fly_to_hotel": fly, "enter_hotel": enter}


def judge_after_receive() -> Dict[str, Any]:
    time.sleep(max(0.5, float(botconfig.ANDROID_STEP_SLEEP_S)))
    img_bgr = vision_bot.screenshot_bgr()
    judged = route_image_intent(img_bgr)
    return {"judged": judged}


def got_baotu_task(judged: Dict[str, Any]) -> bool:
    return str(judged.get("category", "")).strip().lower() in ("mhxy_baotu", "baotu", "mhxy")


def route_to_target() -> Dict[str, Any]:
    extracted = capture_and_extract_baotu_llm()
    llm_qiangdao_name = extracted["llm_qiangdao_name"]
    llm_map_name = extracted["llm_map_name"]
    llm_coord = extracted["llm_coord"]

    qiangdao_plan = datubot_strategies.route_by_map(llm_map_name, llm_coord)
    return {
        "llm_qiangdao_name": llm_qiangdao_name,
        "llm_map_name": llm_map_name,
        "llm_coord": llm_coord,
        "qiangdao_plan": qiangdao_plan,
    }


def excute_datu_once() -> Dict[str, Any]:
    prep = prepare_receive_baotu_task()
    receive = receive_baotu_task()
    plan = route_to_target()
    

    return {"prepare": prep, "receive": receive}


def main() -> None:
    sys_util.clear_debug_capture()
    botconfig.init()
    out = excute_datu_once()
    print(out)


if __name__ == "__main__":
    main()
