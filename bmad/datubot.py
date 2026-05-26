import re
import time
from typing import Dict, Optional, Sequence, Tuple

import cv2
import numpy as np

from .core import config as botconfig
from .device import adb as adb_util
from .device import operator as operator_util
from .core import sys as sys_util
from .vision import bot as vision_bot
from .workflows import routing as route_strategies
from .llm.vision_router import extract_baotu_info, route_image_intent
from .ocr.local import flatten_ocr_text, run_local_ocr
from .core.roi import parse_roi
from .core.common.log_util import log_step
from .core.common.retry_util import retry


def _print_step(name: str, detail: str) -> None:
    log_step("datubot", name, detail)


def _extract_digits(text: str) -> str:
    return "".join(re.findall(r"\d+", str(text or "")))


def _build_battle_timer_variants(cropped: np.ndarray) -> Sequence[Tuple[str, np.ndarray]]:
    upscaled = cv2.resize(cropped, None, fx=3.0, fy=3.0, interpolation=cv2.INTER_CUBIC)
    hsv = cv2.cvtColor(upscaled, cv2.COLOR_BGR2HSV)
    white_mask = cv2.inRange(hsv, (0, 0, 170), (180, 90, 255))
    red_mask_1 = cv2.inRange(hsv, (0, 70, 90), (12, 255, 255))
    red_mask_2 = cv2.inRange(hsv, (165, 70, 90), (180, 255, 255))
    mask = cv2.bitwise_or(white_mask, cv2.bitwise_or(red_mask_1, red_mask_2))
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    return (
        ("raw", cropped),
        ("upscaled", upscaled),
        ("red_white_mask", mask_bgr),
    )


def _ocr_battle_timer_crop(cropped: np.ndarray) -> str:
    best_text = ""
    best_digits = ""
    attempts = []
    for variant_name, variant_image in _build_battle_timer_variants(cropped):
        if bool(botconfig.is_debug()):
            sys_util.save_debug_image(variant_image, f"battle_timer_{variant_name}")
        ocr_result = run_local_ocr(
            variant_image,
            use_det=False,
            use_cls=False,
            use_rec=True,
            log_prefix=f"[datubot][{variant_name}]",
        )
        raw_text = flatten_ocr_text(ocr_result.get("result"))
        digits = _extract_digits(raw_text)
        attempts.append(f"{variant_name}:{raw_text!r}->{digits!r}")
        if digits and (not best_digits or len(digits) >= len(best_digits)):
            best_text = raw_text
            best_digits = digits
        elif not best_text and raw_text:
            best_text = raw_text
    _print_step("battle_timer_ocr_variants", " | ".join(attempts))
    return best_digits or best_text


def _xiaoer_ocr_variant_plan() -> Dict[str, Sequence[str]]:
    return {
        "店小二": ("yellow_text",),
        "挖宝图任务": ("blue_purple_text",),
    }


def _detect_battle_timer_text() -> str:
    roi_text = str(botconfig.BATTLE_CALCULATION_ROI or "").strip()
    if not roi_text:
        raise RuntimeError(f"缺少 {botconfig.KEY_BATTLE_CALCULATION_ROI}，请在 .env 配置，例如 100,100,200,200")

    x1, y1, x2, y2 = parse_roi(roi_text, botconfig.KEY_BATTLE_CALCULATION_ROI)
    img_bgr = vision_bot.screenshot_bgr()
    cropped = img_bgr[y1:y2, x1:x2]
    if cropped.size == 0:
        raise RuntimeError(f"{botconfig.KEY_BATTLE_CALCULATION_ROI} 裁剪结果为空: {[x1, y1, x2, y2]}")
    text = _ocr_battle_timer_crop(cropped)
    _print_step("battle_timer_ocr", f"roi={[x1, y1, x2, y2]} text={text!r}")
    return text


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
        print("店小二模板匹配失败")
        return

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
    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
    tap_transfer = vision_bot.try_tap(
        botconfig.ANDROID_TPL_SYSTEM_TRANSFER,
        threshold=botconfig.ANDROID_THR_SYSTEM_TRANSFER,
    )
    if tap_transfer is None:
        raise RuntimeError("进入酒店失败：未识别到传送按钮")
    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
    _print_step("enter_hotel", f"entered transfer={tap_transfer}")


def receive_baotu_task() -> None:
    max_retry = 3

    def _attempt(i: int):
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
            raise RuntimeError(note)

        vision_bot.try_tap(
            botconfig.ANDROID_TPL_SYSTEM_BACK,
            threshold=botconfig.ANDROID_THR_SYSTEM_BACK,
        )
        _print_step("receive_baotu_task", f"attempt={i} success tap={receive_task.get('tap')}")
        return receive_task

    _, meta = retry(_attempt, times=max_retry, sleep_s=botconfig.ANDROID_STEP_SLEEP_S, name="receive_baotu_task")
    if bool(meta.get("ok")):
        return None
    raise RuntimeError(f"领取宝图任务失败，重试超过{max_retry}次: {meta.get('attempts')}")


def close_to_xiaoer() -> None:
    started_at = time.perf_counter()
    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
    img_bgr = vision_bot.screenshot_bgr()
    ocr_started_at = time.perf_counter()
    tap_info = vision_bot.tap_any_text_by_local_ocr(
        image=img_bgr,
        keywords=["店小二", "挖宝图任务"],
        log_prefix="[datubot]",
        variant_names_by_keyword=_xiaoer_ocr_variant_plan(),
    )
    ocr_elapsed_s = time.perf_counter() - ocr_started_at
    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
    if not bool(tap_info.get("ok")):
        total_elapsed_s = time.perf_counter() - started_at
        print(
            f"店小二/领取宝图任务 OCR 匹配失败: {tap_info} "
            f"ocr_elapsed_s={ocr_elapsed_s:.3f} total_elapsed_s={total_elapsed_s:.3f}"
        )
        return
    click_elapsed_s = tap_info.get("elapsed_s")
    total_elapsed_s = time.perf_counter() - started_at
    time.sleep(1)
    _print_step(
        "close_to_xiaoer",
        f"keyword={tap_info.get('keyword')} text={tap_info.get('text')!r} "
        f"center={tap_info.get('center')} tap={tap_info.get('tap')} "
        f"ocr_elapsed_s={ocr_elapsed_s:.3f} click_elapsed_s={float(click_elapsed_s or 0.0):.3f} "
        f"total_elapsed_s={total_elapsed_s:.3f}",
    )


def capture_and_extract_baotu_llm() -> Tuple[str, str, Optional[Tuple[int, int]]]:
    vision_bot.tap_screen_center(sleep_after=botconfig.ANDROID_STEP_SLEEP_S)
    vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_BACK, threshold=botconfig.ANDROID_THR_SYSTEM_BACK)
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
    matched = vision_bot.find_text_by_local_ocr(
        img_bgr,
        name,
        variant_names=("yellow_text",),
        center_crop_ratio=0.4,
    )
    if matched is None:
        matched = vision_bot.find_text_by_local_ocr(img_bgr, name, variant_names=("yellow_text",))
    if matched is None:
        raise RuntimeError(f"未找到名称: {name}")

    center = matched["center"]
    tap_pt = (int(center[0]), max(0, int(center[1]) - 95))
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
    sys_util.clear_debug_capture()
    cleanup_desktop()
    goto_changan_jiudian()
    receive_baotu_task()
    llm_qiangdao_name, llm_map_name, llm_coord = capture_and_extract_baotu_llm()
    route_to_target(llm_map_name, llm_coord)
    attack_target_with_name(llm_qiangdao_name)
    fighting()




