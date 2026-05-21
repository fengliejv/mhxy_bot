import re
import time
from typing import Any, Optional, Tuple

import botconfig
import adb_util
import operator_util
import sys_util
import vision_bot
import route_strategies as route_strategies
from agent_service import extract_baotu_info, route_image_intent
from local_ocr_util import flatten_ocr_text, run_local_ocr
from roi_util import parse_roi


def _print_step(name: str, detail: str) -> None:
    print(f"[datubot] {name}: {detail}")


def _detect_battle_timer_text() -> str:
    roi_text = str(botconfig.BATTLE_CALCULATION_ROI or "").strip()
    if not roi_text:
        raise RuntimeError(f"缺少 {botconfig.KEY_BATTLE_CALCULATION_ROI}，请在 .env 配置，例如 100,100,200,200")

    x1, y1, x2, y2 = parse_roi(roi_text, botconfig.KEY_BATTLE_CALCULATION_ROI)
    img_bgr = vision_bot.screenshot_bgr()
    cropped = img_bgr[y1:y2, x1:x2]
    ocr_result = run_local_ocr(cropped, use_det=False, use_cls=False, use_rec=True, log_prefix="[datubot]")
    raw_text = flatten_ocr_text(ocr_result.get("result"))
    _print_step("battle_timer_ocr", f"roi={[x1, y1, x2, y2]} raw_text={raw_text!r}")
    return raw_text


def cleanup_desktop() -> None:
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
    tapped = [
        ("close_guide", p_close_guide),
        ("close_task", p_close_task),
        ("hide_dialog", p_hide_dialog),
        ("auto_attack_shrink", p_auto_attack_shrink),
        ("expand", p_expand),
        ("hide_ui_disable", p_hide_ui_disable),
        ("hide_player_disable", p_hide_player_disable),
        ("back", p_back),
        ("map_button", p_map_button),
        ("map_exit", p_map_exit),
    ]
    tapped_names = [name for name, value in tapped if value is not None]
    _print_step("cleanup_desktop", f"tapped={tapped_names}")


def fly_to_hotel() -> None:
    hotel_target = botconfig._parse_xy(botconfig.CHANGAN_FLY_JIUDIAN)
    routed = route_strategies.use_changan_flag_and_tap_nearest(hotel_target)
    if not bool(routed.get("ok")):
        raise RuntimeError("客栈传送点模板匹配失败")
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    _print_step("fly_to_hotel", f"target={hotel_target}")


def go_to_xiaoer() -> None:
    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)

    img_bgr = vision_bot.screenshot_bgr()
    matched = vision_bot.match_first_of_templates(
        img_bgr,
        [botconfig.ANDROID_TPL_NPC_DIANXIAOER_1, botconfig.ANDROID_TPL_NPC_DIANXIAOER_2, botconfig.ANDROID_TPL_NPC_DIANXIAOER_3],
        threshold=botconfig.ANDROID_THR_NPC_XIAOER,
    )
    if matched is None:
        vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
        raise RuntimeError("店小二模板匹配失败")

    tpl = str(matched["template"])
    top_left = matched["top_left"]
    conf = float(matched["confidence"])
    w, h = vision_bot.get_template_wh(tpl)
    tap_center = (int(top_left[0] + w / 2), int(top_left[1] + h / 2))
    adb_util.tap(tap_center[0], tap_center[1])

    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
    _print_step(
        "go_to_xiaoer",
        f"template={tpl} confidence={conf:.3f} tap={tap_center}",
    )


def enter_hotel() -> None:
    vision_bot.tap_template(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
    vision_bot.tap_template(botconfig.ANDROID_TPL_CHANGAN_HOTEL_DOOR, threshold=botconfig.ANDROID_THR_CHANGAN_HOTEL_DOOR)
    vision_bot.tap_template(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
    _print_step("enter_hotel", "entered")


def receive_baotu_task() -> None:
    max_retry = 5
    attempt_notes = []
    for i in range(1, max_retry + 1):
        _print_step("receive_baotu_task", f"attempt={i} start")
        close_to_xiaoer()
        go_to_xiaoer()
        receive_task = vision_bot.try_tap_template(
            template_path=botconfig.ANDROID_TPL_BAOTU_RECEIVE_TASK,
            threshold=botconfig.ANDROID_THR_BAOTU_RECEIVE_TASK,
        )
        if receive_task is None:
            has_daoju = vision_bot.template_exists(
                template_path=botconfig.ANDROID_TPL_MENU_DAOJU,
                threshold=botconfig.ANDROID_MATCH_THRESHOLD,
            )
            note = f"attempt={i} receive_task_missing has_daoju_icon={has_daoju}"
            if not has_daoju:
                img_bgr = vision_bot.screenshot_bgr()
                random_task = route_image_intent(img_bgr)
                note = f"{note} random_task={random_task}"
            _print_step("receive_baotu_task", note)
            attempt_notes.append(note)
            continue

        vision_bot.try_tap(
            botconfig.ANDROID_TPL_SYSTEM_BACK,
            threshold=botconfig.ANDROID_THR_SYSTEM_BACK,
        )
        _print_step("receive_baotu_task", f"attempt={i} success tap={receive_task.get('tap')}")
        return None

    raise RuntimeError(f"领取宝图任务失败，重试超过{max_retry}次: {attempt_notes}")


def close_to_xiaoer() -> None:
    p_map_button = vision_bot.try_tap_best(
        [botconfig.ANDROID_TPL_MAP_BUTTON, botconfig.ANDROID_TPL_MAP_BUTTON_2],
        threshold=botconfig.ANDROID_THR_MAP_BUTTON,
    )
    if p_map_button is None:
        raise RuntimeError("地图按钮模板匹配失败")

    vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_SEARCH_ICON,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_INPUT_ICON,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )

    adb_util.ime_set(botconfig.ANDROID_ADB_IME_ID)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    adb_util.adbkeyboard_input_text("店小二")
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)
    adb_util.ime_set(botconfig.ANDROID_SOGOU_IME_ID)
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)

    vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_ON_THE_WAY,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    vision_bot.tap_template(
        botconfig.ANDROID_TPL_MAP_EXIT,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    arrival = vision_bot.wait_until_arrived_by_coord()
    _print_step(
        "close_to_xiaoer",
        f"target=店小二 arrived={bool(arrival.get('arrived'))} coord={arrival.get('coord')} samples={arrival.get('samples')}",
    )
    if not bool(arrival.get("arrived")):
        raise RuntimeError(f"前往店小二失败: {arrival}")


def capture_and_extract_baotu_llm() -> Tuple[str, str, Optional[Tuple[int, int]]]:
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
    _print_step(
        "capture_and_extract_baotu_llm",
        f"qiangdao_name={llm_qiangdao_name} map_name={llm_map_name} coord={llm_coord}",
    )
    return llm_qiangdao_name, llm_map_name, llm_coord


def goto_changan_jiudian() -> None:
    fly_to_hotel()
    enter_hotel()
    _print_step("prepare_receive_baotu_task", "done")

def route_to_target(llm_map_name: str, llm_coord: Optional[Tuple[int, int]]) -> None:
    plan = route_strategies.route_by_map(llm_map_name, llm_coord)
    _print_step(
        "route_to_target",
        f"map_name={llm_map_name} coord={llm_coord} "
        f"ok={plan.get('ok')} reason={plan.get('reason')}",
    )
    if not bool(plan.get("ok")):
        raise RuntimeError(f"前往目标失败: {plan}")

def attack_target_with_name(name: str) -> None:
    name = str(name or "").strip()
    if not name:
        raise RuntimeError("缺少名称，无法发起战斗")

    img_bgr = vision_bot.screenshot_bgr()
    matched = vision_bot.find_text_by_local_ocr(img_bgr, name)
    if matched is None:
        raise RuntimeError(f"未找到名称: {name}")

    center = matched["center"]
    tap_pt = (int(center[0]), max(0, int(center[1]) - 10))
    adb_util.tap(tap_pt[0], tap_pt[1])
    time.sleep(botconfig.ANDROID_STEP_SLEEP_S)

    talk = vision_bot.tap_template(
        botconfig.ANDROID_TPL_BAOTU_ATTACK_TALK,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    _print_step(
        "attack_target",
        f"name={name} center={center} tap={tap_pt} talk={talk}",
    )

def fighting_attack_once() -> None:
    tap_hero = operator_util.tap_template(
        botconfig.ANDROID_TPL_ZHAOHUANSHOU_QIANGDAO,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    time.sleep(0.5)
    tap_pet = operator_util.tap_template(
        botconfig.ANDROID_TPL_ZHAOHUANSHOU_QIANGDAO,
        threshold=botconfig.ANDROID_MATCH_THRESHOLD,
    )
    _print_step(
        "fighting_attack_once",
        f"hero={tap_hero} pet={tap_pet}",
    )

def fighting() -> None:
    max_rounds = 3
    for round_idx in range(1, max_rounds + 1):
        raw_text = _detect_battle_timer_text()
        if re.search(r"\d", raw_text) is None:
            _print_step("fighting", f"round={round_idx} timer_not_found battle_finished")
            return

        _print_step("fighting", f"round={round_idx} timer={raw_text!r} attack")
        fighting_attack_once()

        if round_idx < max_rounds:
            time.sleep(5.0)

    _print_step("fighting", f"reached_max_rounds={max_rounds}")

def excute_datu_once() -> None:
    cleanup_desktop()
    goto_changan_jiudian()
    receive_baotu_task()
    llm_qiangdao_name, llm_map_name, llm_coord = capture_and_extract_baotu_llm()
    route_to_target(llm_map_name, llm_coord)
    attack_target_with_name(llm_qiangdao_name)
    fighting()


def main() -> None:
    sys_util.clear_debug_capture()
    botconfig.init()
    resp = run_local_ocr("assets/materia/xiaorenwu.jpg", use_det=True, use_cls=False, use_rec=True, log_prefix="[vision_bot]")

    # matched = vision_bot.find_text_by_local_ocr("assets/materia/xiaorenwu.jpg", "店小二")
    print(resp)
    # out = excute_datu_once()
    # route_strategies.route_by_map("化生寺", (60,55))
    # print(plan)
    # print(out)


if __name__ == "__main__":
    main()
