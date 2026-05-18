import time
from typing import Any, Dict, Optional, Tuple

import botconfig
import vision_bot


def _parse_coord_text(text: str, name: str) -> Tuple[int, int]:
    s = str(text or "").strip()
    if not s:
        raise RuntimeError(f"缺少 {name} 坐标配置，格式 x,y")
    s = s.replace("，", ",").replace(" ", ",")
    parts = [p.strip() for p in s.split(",") if p.strip()]
    if len(parts) < 2:
        raise RuntimeError(f"{name} 坐标格式错误，期望 x,y")
    return int(parts[0]), int(parts[1])


def fly_to(destination: str) -> Dict[str, Any]:
    dest = str(destination or "").strip()
    if not dest:
        return {"ok": False, "reason": "empty_destination", "destination": destination}

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
        return {"ok": False, "reason": "unsupported_destination", "destination": destination}

    tpl_feixingfu = "assets/android/daoju/feixingfu.png"
    tpl_close_bag = "assets/android/daoju/jiemian/guanbi.png"

    tap_menu = vision_bot.tap_template(botconfig.ANDROID_TPL_MENU_DAOJU, threshold=botconfig.ANDROID_THR_MENU_DAOJU)
    tap_feixingfu = vision_bot.tap_template(tpl_feixingfu, threshold=botconfig.ANDROID_THR_PROP_FEIXINGFU)
    tap_use = vision_bot.tap_template(botconfig.ANDROID_TPL_PROP_USE, threshold=botconfig.ANDROID_THR_PROP_USE)
    tap_map = vision_bot.tap_template(map_tpl, threshold=botconfig.ANDROID_THR_FEIXINGFU_MAP)
    tap_close = vision_bot.try_tap(tpl_close_bag, threshold=botconfig.ANDROID_THR_DAOJU_CLOSE)
    return {
        "ok": True,
        "strategy": "fly",
        "destination": destination,
        "map_template": map_tpl,
        "tap_menu_daoju": tap_menu,
        "tap_feixingfu": tap_feixingfu,
        "tap_use": tap_use,
        "tap_map": tap_map,
        "tap_close_bag": tap_close,
    }


def route_to_shituo(coord: Tuple[int, int]) -> Dict[str, Any]:
    if coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": coord}

    fly = fly_to("朱紫国")
    if not bool(fly.get("ok")):
        return {"ok": False, "reason": "fly_to_zhuziguo_failed", "fly": fly}

    nav_zhuziguo_to_transfer = vision_bot.navigate_to_coord(x=7, y=4)

    tpl_transfer = r"assets\android\system\transfer.jpg"
    max_retry = int(botconfig.ANDROID_TRANSFER_RETRY)
    retry_sleep_s = float(botconfig.ANDROID_TRANSFER_RETRY_SLEEP_S)

    tap_transfer_1 = None
    for _ in range(max(1, max_retry)):
        tap_transfer_1 = vision_bot.try_tap(tpl_transfer, threshold=botconfig.ANDROID_THR_SYSTEM_TRANSFER)
        if tap_transfer_1 is not None:
            break
        time.sleep(max(0.1, retry_sleep_s))
    if tap_transfer_1 is None:
        return {"ok": False, "reason": "transfer_not_found_1", "fly": fly, "navigate": nav_zhuziguo_to_transfer}

    time.sleep(max(0.5, float(botconfig.ANDROID_STEP_SLEEP_S)))
    detected_after_1 = vision_bot.detect_current_map_by_roi()

    jingwai_xy = _parse_coord_text(
        botconfig.env_str("JINGWAI_TO_SHITUO", botconfig.JINGWAI_TO_SHITUO),
        "JINGWAI_TO_SHITUO",
    )
    nav_jingwai_to_shituo_entry = vision_bot.navigate_to_coord(x=jingwai_xy[0], y=jingwai_xy[1])

    tap_transfer_2 = None
    for _ in range(max(1, max_retry)):
        tap_transfer_2 = vision_bot.try_tap(tpl_transfer, threshold=botconfig.ANDROID_THR_SYSTEM_TRANSFER)
        if tap_transfer_2 is not None:
            break
        time.sleep(max(0.1, retry_sleep_s))
    if tap_transfer_2 is None:
        return {
            "ok": False,
            "reason": "transfer_not_found_2",
            "fly": fly,
            "navigate_zhuziguo_to_transfer": nav_zhuziguo_to_transfer,
            "detected_after_transfer_1": detected_after_1,
            "navigate_jingwai_to_shituo_entry": nav_jingwai_to_shituo_entry,
        }

    time.sleep(max(0.5, float(botconfig.ANDROID_STEP_SLEEP_S)))
    detected_after_2 = vision_bot.detect_current_map_by_roi()

    nav_in_shituo_to_target = vision_bot.navigate_to_coord(x=int(coord[0]), y=int(coord[1]))

    return {
        "ok": True,
        "strategy": "shituo",
        "coord": coord,
        "fly_to_zhuziguo": fly,
        "navigate_zhuziguo_to_transfer": nav_zhuziguo_to_transfer,
        "tap_transfer_1": tap_transfer_1,
        "detected_after_transfer_1": detected_after_1,
        "jingwai_to_shituo": jingwai_xy,
        "navigate_jingwai_to_shituo_entry": nav_jingwai_to_shituo_entry,
        "tap_transfer_2": tap_transfer_2,
        "detected_after_transfer_2": detected_after_2,
        "navigate_in_shituo_to_target": nav_in_shituo_to_target,
    }


def route_by_map(map_name: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
    dest = str(map_name or "").strip()
    if dest in ("狮驼岭", "大唐境外"):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return route_to_shituo((int(coord[0]), int(coord[1])))

    if dest in ("建邺城", "长寿村", "朱紫国", "傲来国", "宝象国", "女儿村", "西梁女国", "长安城"):
        return fly_to(dest)

    return {"ok": False, "reason": "not_implemented", "map_name": map_name, "coord": coord}
