from typing import Any, Callable, Dict, Optional, Tuple

import adb_util
import botconfig
from image_matcher import match_template
import operator_util
import vision_bot


def _navigate_to_config_coord(coord_text: str) -> Tuple[int, int]:
    xy = botconfig._parse_xy(coord_text)
    if xy is None:
        raise RuntimeError("坐标配置格式错误，期望 x,y")
    vision_bot.navigate_to_coord(x=xy[0], y=xy[1])
    return xy


def _tap_system_transfer_once() -> Optional[Tuple[int, int]]:
    return operator_util.try_tap(
        botconfig.ANDROID_TPL_SYSTEM_TRANSFER,
        threshold=botconfig.ANDROID_THR_SYSTEM_TRANSFER,
    )


def _parse_required_config_coord(coord_text: str, config_name: str) -> Tuple[int, int]:
    xy = botconfig._parse_xy(coord_text)
    if xy is None:
        raise RuntimeError(f"{config_name} 坐标配置格式错误，期望 x,y")
    return xy


def _success_result(strategy: str, coord: Tuple[int, int]) -> Dict[str, Any]:
    return {
        "ok": True,
        "strategy": strategy,
        "coord": coord,
    }


def _normalize_coord(coord: Optional[Tuple[int, int]]) -> Optional[Tuple[int, int]]:
    if coord is None:
        return None
    return int(coord[0]), int(coord[1])


def _route_with_required_coord(
    map_name: str,
    coord: Optional[Tuple[int, int]],
    route_func: Callable[[Tuple[int, int]], Dict[str, Any]],
) -> Dict[str, Any]:
    normalized = _normalize_coord(coord)
    if normalized is None:
        return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
    return route_func(normalized)


def _route_via_zhuziguo_to_jingwai_transfer(
    entry_coord_text: str,
    target_coord: Tuple[int, int],
    strategy: str,
) -> Dict[str, Any]:
    if target_coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": target_coord}

    fly = fly_to("朱紫国")
    if not bool(fly.get("ok")):
        return {"ok": False, "reason": "fly_to_zhuziguo_failed", "fly": fly}

    zhuziguo_to_jingwai = _navigate_to_config_coord(botconfig.ZHUZI_TO_JINGWAI)
    tap_transfer_1 = _tap_system_transfer_once()
    if tap_transfer_1 is None:
        return {"ok": False, "reason": "transfer_not_found_1", "fly": fly}

    jingwai_xy = _navigate_to_config_coord(entry_coord_text)

    tap_transfer_2 = _tap_system_transfer_once()
    if tap_transfer_2 is None:
        return {
            "ok": False,
            "reason": "transfer_not_found_2",
            "fly": fly,
        }

    vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    return {
        "ok": True,
        "strategy": strategy,
        "coord": target_coord,
        "fly": fly,
        "zhuziguo_to_jingwai": zhuziguo_to_jingwai,
        "tap_transfer_to_jingwai": tap_transfer_1,
        "jingwai_entry_coord": jingwai_xy,
        "tap_transfer_to_target": tap_transfer_2,
    }


def _route_via_single_transfer(
    start_destination: str,
    entry_coord_text: str,
    target_coord: Tuple[int, int],
    strategy: str,
) -> Dict[str, Any]:
    if target_coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": target_coord}

    fly = fly_to(start_destination)
    if not bool(fly.get("ok")):
        return {"ok": False, "reason": f"fly_to_{start_destination}_failed", "fly": fly}

    entry_xy = _navigate_to_config_coord(entry_coord_text)

    tap_transfer = _tap_system_transfer_once()
    if tap_transfer is None:
        return {
            "ok": False,
            "reason": "transfer_not_found",
            "fly": fly,
        }

    vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    return {
        "ok": True,
        "strategy": strategy,
        "coord": target_coord,
        "fly": fly,
        "entry_coord": entry_xy,
        "tap_transfer": tap_transfer,
    }


def _route_via_direct_fly(destination: str, target_coord: Tuple[int, int]) -> Dict[str, Any]:
    fly = fly_to(destination)
    if not bool(fly.get("ok")):
        return {"ok": False, "reason": f"fly_to_{destination}_failed", "fly": fly}

    vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    return {
        "ok": True,
        "strategy": "fly_and_navigate",
        "destination": destination,
        "coord": target_coord,
        "fly": fly,
    }


def _route_via_single_transfer_with_log(
    route_name: str,
    start_destination: str,
    entry_coord_text: str,
    target_coord: Tuple[int, int],
    strategy: str,
    entry_label: str,
) -> Dict[str, Any]:
    routed = _route_via_single_transfer(start_destination, entry_coord_text, target_coord, strategy=strategy)
    if not bool(routed.get("ok")):
        print(f"[{route_name}] single_transfer failed reason={routed.get('reason')}")
        return routed
    print(
        f"[{route_name}] {entry_label}={routed.get('entry_coord')} "
        f"tap_transfer={routed.get('tap_transfer')} target={target_coord}"
    )
    return _success_result(strategy, target_coord)


def _route_via_existing_route_and_transfer(
    route_name: str,
    parent_route: Callable[[Tuple[int, int]], Dict[str, Any]],
    parent_route_name: str,
    parent_fail_reason: str,
    entry_coord_text: str,
    config_name: str,
    target_coord: Tuple[int, int],
    strategy: str,
    entry_label: str,
) -> Dict[str, Any]:
    if target_coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": target_coord}

    entry_coord = _parse_required_config_coord(entry_coord_text, config_name)
    routed = parent_route(entry_coord)
    if not bool(routed.get("ok")):
        print(f"[{route_name}] {parent_route_name} failed reason={routed.get('reason')}")
        return {"ok": False, "reason": parent_fail_reason}

    tap_transfer = _tap_system_transfer_once()
    if tap_transfer is None:
        print(f"[{route_name}] transfer_not_found")
        return {"ok": False, "reason": "transfer_not_found"}

    vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    print(
        f"[{route_name}] {entry_label}={entry_coord} "
        f"tap_transfer={tap_transfer} target={target_coord}"
    )
    return _success_result(strategy, target_coord)


def _route_via_existing_route_and_npc(
    route_name: str,
    parent_route: Callable[[Tuple[int, int]], Dict[str, Any]],
    parent_route_name: str,
    parent_fail_reason: str,
    entry_coord_text: str,
    config_name: str,
    npc_template: str,
    target_coord: Tuple[int, int],
    strategy: str,
    entry_label: str,
) -> Dict[str, Any]:
    if target_coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": target_coord}

    entry_coord = _parse_required_config_coord(entry_coord_text, config_name)
    routed = parent_route(entry_coord)
    if not bool(routed.get("ok")):
        print(f"[{route_name}] {parent_route_name} failed reason={routed.get('reason')}")
        return {"ok": False, "reason": parent_fail_reason}

    tap_npc = operator_util.tap_template(npc_template)
    tap_woyaoqu = operator_util.tap_template(botconfig.ANDROID_TPL_CHAT_WOYAOQU)
    vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    print(
        f"[{route_name}] {entry_label}={entry_coord} tap_npc={tap_npc} "
        f"tap_woyaoqu={tap_woyaoqu} target={target_coord}"
    )
    return _success_result(strategy, target_coord)


def _route_via_zhuziguo_to_jingwai_with_log(
    route_name: str,
    entry_coord_text: str,
    target_coord: Tuple[int, int],
    strategy: str,
    entry_label: str,
) -> Dict[str, Any]:
    if target_coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": target_coord}

    routed = _route_via_zhuziguo_to_jingwai_transfer(entry_coord_text, target_coord, strategy=strategy)
    if not bool(routed.get("ok")):
        print(f"[{route_name}] route_via_zhuziguo_to_jingwai failed reason={routed.get('reason')}")
        return routed
    print(
        f"[{route_name}] zhuziguo_to_jingwai={routed.get('zhuziguo_to_jingwai')} "
        f"tap_transfer_to_jingwai={routed.get('tap_transfer_to_jingwai')} "
        f"{entry_label}={routed.get('jingwai_entry_coord')} "
        f"tap_transfer_to_target={routed.get('tap_transfer_to_target')} "
        f"target={target_coord}"
    )
    return _success_result(strategy, target_coord)


def _use_changan_flag_to_entry(
    route_name: str,
    entry_coord_text: str,
    config_name: str,
    fail_reason: str,
) -> Dict[str, Any]:
    entry_coord = _parse_required_config_coord(entry_coord_text, config_name)
    changan_flag_step = use_changan_flag_and_tap_nearest(entry_coord)
    if not bool(changan_flag_step.get("ok")):
        print(f"[{route_name}] use_changan_flag failed reason={changan_flag_step.get('reason')}")
        return {"ok": False, "reason": fail_reason}

    print(f"[{route_name}] changan_flag target={entry_coord}")
    return {
        "ok": True,
        "entry_coord": entry_coord,
    }


def _tap_nearest_match(template_path: str, target_xy: Tuple[int, int], threshold: float) -> Optional[Dict[str, Any]]:
    img_bgr = operator_util.screenshot_bgr()
    ok, _, locations = match_template(img_bgr, template_path, threshold=threshold, find_all=True)
    if not ok or not locations:
        return None

    tpl_w, tpl_h = operator_util.get_template_wh(template_path)
    best = None
    for top_left, conf in locations:
        cx = int(top_left[0] + tpl_w / 2)
        cy = int(top_left[1] + tpl_h / 2)
        dx = cx - target_xy[0]
        dy = cy - target_xy[1]
        dist2 = dx * dx + dy * dy
        item = {
            "top_left": top_left,
            "confidence": float(conf),
            "center": (cx, cy),
            "dist2": int(dist2),
        }
        if best is None or item["dist2"] < best["dist2"]:
            best = item

    adb_util.tap(best["center"][0], best["center"][1])
    return {"target": target_xy, "best": best, "count": len(locations)}


def _open_bag_and_use_prop(prop_template: str, prop_threshold: float, prop_name: str) -> None:
    tap_menu = operator_util.tap_template(botconfig.ANDROID_TPL_MENU_DAOJU, threshold=botconfig.ANDROID_THR_MENU_DAOJU)
    tap_prop = operator_util.tap_template(prop_template, threshold=prop_threshold)
    tap_use = operator_util.tap_template(botconfig.ANDROID_TPL_PROP_USE, threshold=botconfig.ANDROID_THR_PROP_USE)
    print(
        f"[_open_bag_and_use_prop] prop={prop_name} tap_menu_daoju={tap_menu} "
        f"tap_prop={tap_prop} tap_use={tap_use}"
    )


def use_changan_flag_and_tap_nearest(target_coord: Tuple[int, int]) -> Dict[str, Any]:
    _open_bag_and_use_prop(
        botconfig.ANDROID_TPL_PROP_CHANGAN_FLAG,
        botconfig.ANDROID_THR_PROP_CHANGAN_FLAG,
        "changan_flag",
    )
    nearest = _tap_nearest_match(
        botconfig.ANDROID_TPL_MAP_TELEPORT_POINT,
        target_coord,
        threshold=botconfig.ANDROID_THR_MAP_TELEPORT_POINT,
    )
    if nearest is None:
        return {
            "ok": False,
            "reason": "teleport_point_not_found",
            "target": target_coord,
        }
    best = nearest["best"]
    print(
        f"[use_changan_flag_and_tap_nearest] target={target_coord} selected_center={best['center']} "
        f"confidence={best['confidence']:.3f} candidates={nearest['count']}"
    )
    return {
        "ok": True,
        "target": target_coord,
    }


def fly_to(destination: str) -> Dict[str, Any]:
    dest = str(destination or "").strip()
    if not dest:
        return {"ok": False, "reason": "empty_destination", "destination": destination}

    map_tpl_by_dest = {
        "傲来国": botconfig.ANDROID_TPL_FEIXINGFU_MAP_AOLAIGUO,
        "宝象国": botconfig.ANDROID_TPL_FEIXINGFU_MAP_BAOXIANGGUO,
        "长安城": botconfig.ANDROID_TPL_FEIXINGFU_MAP_CHANGANCHENG,
        "长寿村": botconfig.ANDROID_TPL_FEIXINGFU_MAP_CHANGSHOUCUN,
        "建邺城": botconfig.ANDROID_TPL_FEIXINGFU_MAP_JIANYECHENG,
        "朱紫国": botconfig.ANDROID_TPL_FEIXINGFU_MAP_ZHUZIGUO,
        "西梁女国": botconfig.ANDROID_TPL_FEIXINGFU_MAP_XILIANGNVGUO,
    }
    map_tpl = map_tpl_by_dest.get(dest)
    if not map_tpl:
        return {"ok": False, "reason": "unsupported_destination", "destination": destination}

    _open_bag_and_use_prop(
        botconfig.ANDROID_TPL_PROP_FEIXINGFU,
        botconfig.ANDROID_THR_PROP_FEIXINGFU,
        "feixingfu",
    )
    tap_map = operator_util.tap_template(map_tpl, threshold=botconfig.ANDROID_THR_FEIXINGFU_MAP)
    tap_close = operator_util.try_tap(botconfig.ANDROID_TPL_DAOJU_CLOSE, threshold=botconfig.ANDROID_THR_DAOJU_CLOSE)
    print(
        f"[fly_to] destination={destination} map_template={map_tpl} "
        f"tap_map={tap_map} tap_close_bag={tap_close}"
    )
    return {
        "ok": True,
        "strategy": "fly",
        "destination": destination,
    }


def route_to_shituo(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_zhuziguo_to_jingwai_with_log(
        route_name="route_to_shituo",
        entry_coord_text=botconfig.JINGWAI_TO_SHITUO,
        target_coord=coord,
        strategy="shituo",
        entry_label="jingwai_to_shituo",
    )


def route_to_mowang(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_zhuziguo_to_jingwai_with_log(
        route_name="route_to_mowang",
        entry_coord_text=botconfig.JINGWAI_TO_MOWANG,
        target_coord=coord,
        strategy="mowang",
        entry_label="jingwai_to_mowang",
    )

def route_to_huasheng(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_single_transfer_with_log(
        route_name="route_to_huasheng",
        start_destination="长安城",
        entry_coord_text=botconfig.CHANGAN_TO_HUANSHENG,
        target_coord=coord,
        strategy="huasheng",
        entry_label="changan_to_huasheng",
    )

def route_to_datangguojing(coord: Tuple[int, int]) -> Dict[str, Any]:
    if coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": coord}

    flag_entry = _use_changan_flag_to_entry(
        route_name="route_to_datangguojing",
        entry_coord_text=botconfig.CHANGAN_FLY_YIZHANLAOBAN,
        config_name="CHANGAN_FLY_YIZHANLAOBAN",
        fail_reason="yizhanlaoban_teleport_not_found",
    )
    if not bool(flag_entry.get("ok")):
        return flag_entry

    tap_expand = vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_EXPAND, threshold=botconfig.ANDROID_THR_SYSTEM_EXPAND)
    tap_hide_ui = (
        vision_bot.try_tap(botconfig.ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE, threshold=botconfig.ANDROID_THR_SYSTEM_HIDE_UI_DISABLE)
        if tap_expand is not None
        else None
    )
    tap_npc = operator_util.tap_template(botconfig.ANDROID_TPL_NPC_CHANGAN_YIZHANLAOBAN)
    tap_woyaoqu = operator_util.tap_template(botconfig.ANDROID_TPL_CHAT_WOYAOQU)
    vision_bot.navigate_to_coord(x=int(coord[0]), y=int(coord[1]))
    print(
        f"[route_to_datangguojing] tap_expand={tap_expand} tap_hide_ui_disable={tap_hide_ui} "
        f"tap_npc={tap_npc} tap_woyaoqu={tap_woyaoqu} target={coord}"
    )

    return _success_result("datangguojing", coord)


def route_to_jiangnanyewai(coord: Tuple[int, int]) -> Dict[str, Any]:
    if coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": coord}

    flag_entry = _use_changan_flag_to_entry(
        route_name="route_to_jiangnanyewai",
        entry_coord_text=botconfig.CHANGAN_FLY_YEWAI,
        config_name="CHANGAN_FLY_YEWAI",
        fail_reason="yewai_entry_not_found",
    )
    if not bool(flag_entry.get("ok")):
        return flag_entry

    changan_to_jiangnanyewai = _navigate_to_config_coord(botconfig.CHANGAN_TO_JIANGNANYEWAI)

    tap_transfer = _tap_system_transfer_once()
    if tap_transfer is None:
        print("[route_to_jiangnanyewai] transfer_not_found")
        return {"ok": False, "reason": "transfer_not_found"}

    vision_bot.navigate_to_coord(x=int(coord[0]), y=int(coord[1]))
    print(
        f"[route_to_jiangnanyewai] changan_to_jiangnanyewai={changan_to_jiangnanyewai} "
        f"tap_transfer={tap_transfer} target={coord}"
    )
    return _success_result("jiangnanyewai", coord)


def route_to_putuo(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_npc(
        route_name="route_to_putuo",
        parent_route=route_to_datangguojing,
        parent_route_name="route_to_datangguojing",
        parent_fail_reason="route_to_datangguojing_failed",
        entry_coord_text=botconfig.GUOJING_TO_PUTUO,
        config_name="GUOJING_TO_PUTUO",
        npc_template=botconfig.ANDROID_TPL_NPC_JIEYINXIANNV,
        target_coord=coord,
        strategy="putuo",
        entry_label="guojing_to_putuo",
    )

def route_to_difu(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_transfer(
        route_name="route_to_difu",
        parent_route=route_to_datangguojing,
        parent_route_name="route_to_datangguojing",
        parent_fail_reason="route_to_datangguojing_failed",
        entry_coord_text=botconfig.GUOJING_TO_DIFU,
        config_name="GUOJING_TO_DIFU",
        target_coord=coord,
        strategy="difu",
        entry_label="guojing_to_difu",
    )

def route_to_donghaiwan(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_single_transfer_with_log(
        route_name="route_to_donghaiwan",
        start_destination="建邺城",
        entry_coord_text=botconfig.JIANYE_TO_DONGHAIWAN,
        target_coord=coord,
        strategy="donghaiwan",
        entry_label="jianye_to_donghaiwan",
    )

def route_to_nver(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_single_transfer_with_log(
        route_name="route_to_nver",
        start_destination="傲来国",
        entry_coord_text=botconfig.AOLAI_TO_NVER,
        target_coord=coord,
        strategy="nver",
        entry_label="aolai_to_nver",
    )

def route_to_tiangong(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_npc(
        route_name="route_to_tiangong",
        parent_route=route_to_changshoujiaowai,
        parent_route_name="route_to_changshoujiaowai",
        parent_fail_reason="route_to_changshoujiaowai_failed",
        entry_coord_text=botconfig.CHANGSHOUJIAOWAI_TO_TIANGONG,
        config_name="CHANGSHOUJIAOWAI_TO_TIANGONG",
        npc_template=botconfig.ANDROID_TPL_NPC_TIANJIANG,
        target_coord=coord,
        strategy="tiangong",
        entry_label="changshoujiaowai_to_tiangong",
    )

def route_to_longgong(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_npc(
        route_name="route_to_longgong",
        parent_route=route_to_donghaiwan,
        parent_route_name="route_to_donghaiwan",
        parent_fail_reason="route_to_donghaiwan_failed",
        entry_coord_text=botconfig.DONGHAIWAN_TO_LONGGONG,
        config_name="DONGHAIWAN_TO_LONGGONG",
        npc_template=botconfig.ANDROID_TPL_NPC_LAOXIA,
        target_coord=coord,
        strategy="longgong",
        entry_label="donghaiwan_to_longgong",
    )


def route_to_fangcun(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_single_transfer_with_log(
        route_name="route_to_fangcun",
        start_destination="长寿村",
        entry_coord_text=botconfig.CHANGSHOU_TO_FANGCUN,
        target_coord=coord,
        strategy="fangcun",
        entry_label="changshou_to_fangcun",
    )

def route_to_changshoujiaowai(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_single_transfer_with_log(
        route_name="route_to_changshoujiaowai",
        start_destination="长寿村",
        entry_coord_text=botconfig.CHANGSHOU_TO_CHANGSHOUJIAOWAI,
        target_coord=coord,
        strategy="changshoujiaowai",
        entry_label="changshou_to_changshoujiaowai",
    )

def route_to_datangjingwai_via_guojing(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_transfer(
        route_name="route_to_datangjingwai_via_guojing",
        parent_route=route_to_datangguojing,
        parent_route_name="route_to_datangguojing",
        parent_fail_reason="route_to_datangguojing_failed",
        entry_coord_text=botconfig.GUOJING_TO_JINGWAI,
        config_name="GUOJING_TO_JINGWAI",
        target_coord=coord,
        strategy="datangjingwai",
        entry_label="guojing_to_jingwai",
    )


def route_to_wuzhuang(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_transfer(
        route_name="route_to_wuzhuang",
        parent_route=route_to_datangjingwai_via_guojing,
        parent_route_name="route_to_datangjingwai_via_guojing",
        parent_fail_reason="route_to_datangjingwai_via_guojing_failed",
        entry_coord_text=botconfig.JINGWAI_TO_WUZHUANG,
        config_name="JINGWAI_TO_WUZHUANG",
        target_coord=coord,
        strategy="wuzhuang",
        entry_label="jingwai_to_wuzhuang",
    )

def route_to_pansi(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_existing_route_and_transfer(
        route_name="route_to_pansi",
        parent_route=route_to_datangjingwai_via_guojing,
        parent_route_name="route_to_datangjingwai_via_guojing",
        parent_fail_reason="route_to_datangjingwai_via_guojing_failed",
        entry_coord_text=botconfig.JINGWAI_TO_PANSI,
        config_name="JINGWAI_TO_PANSI",
        target_coord=coord,
        strategy="pansi",
        entry_label="jingwai_to_pansi",
    )

def route_to_huaguo(coord: Tuple[int, int]) -> Dict[str, Any]:
    return _route_via_single_transfer_with_log(
        route_name="route_to_huaguo",
        start_destination="傲来国",
        entry_coord_text=botconfig.AOLAI_TO_HUAGUO,
        target_coord=coord,
        strategy="huaguo",
        entry_label="aolai_to_huaguo",
    )

def route_by_map(map_name: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
    dest = str(map_name or "").strip()
    route_handlers = {
        "狮驼岭": route_to_shituo,
        "魔王寨": route_to_mowang,
        "化生寺": route_to_huasheng,
        "东海湾": route_to_donghaiwan,
        "龙宫": route_to_longgong,
        "东海龙宫": route_to_longgong,
        "天宫": route_to_tiangong,
        "女儿村": route_to_nver,
        "大唐国境": route_to_datangguojing,
        "江南野外": route_to_jiangnanyewai,
        "普陀山": route_to_putuo,
        "阴曹地府": route_to_difu,
        "方寸山": route_to_fangcun,
        "花果山": route_to_huaguo,
        "长寿郊外": route_to_changshoujiaowai,
        "大唐境外": route_to_datangjingwai_via_guojing,
        "境外": route_to_datangjingwai_via_guojing,
        "五庄观": route_to_wuzhuang,
        "盘丝洞": route_to_pansi,
        "盘丝岭": route_to_pansi,
    }
    if dest in route_handlers:
        return _route_with_required_coord(map_name, coord, route_handlers[dest])

    if dest in ("建邺城", "长寿村", "朱紫国", "傲来国", "宝象国", "长安城", "西梁女国"):
        normalized = _normalize_coord(coord)
        if normalized is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return _route_via_direct_fly(dest, normalized)

    return {"ok": False, "reason": "not_implemented", "map_name": map_name, "coord": coord}
