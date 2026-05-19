from typing import Any, Dict, Optional, Tuple

import botconfig
import operator_util
import vision_bot


def _navigate_to_config_coord(coord_text: str) -> Dict[str, Any]:
    xy = botconfig._parse_xy(coord_text)
    if xy is None:
        raise RuntimeError("坐标配置格式错误，期望 x,y")
    nav = vision_bot.navigate_to_coord(x=xy[0], y=xy[1])
    return {"coord": xy, "navigate": nav}


def _tap_system_transfer_once() -> Optional[Tuple[int, int]]:
    return operator_util.try_tap(
        botconfig.ANDROID_TPL_SYSTEM_TRANSFER,
        threshold=botconfig.ANDROID_THR_SYSTEM_TRANSFER,
    )


def _route_via_jingwai_transfer(entry_coord_text: str, target_coord: Tuple[int, int], strategy: str) -> Dict[str, Any]:
    if target_coord is None:
        return {"ok": False, "reason": "missing_target_coord", "coord": target_coord}

    fly = fly_to("朱紫国")
    if not bool(fly.get("ok")):
        return {"ok": False, "reason": "fly_to_zhuziguo_failed", "fly": fly}

    zhuziguo_step = _navigate_to_config_coord(botconfig.ZHUZI_TO_JINGWAI)
    tap_transfer_1 = _tap_system_transfer_once()
    if tap_transfer_1 is None:
        return {"ok": False, "reason": "transfer_not_found_1", "fly": fly, "navigate": zhuziguo_step["navigate"]}

    jingwai_step = _navigate_to_config_coord(entry_coord_text)
    jingwai_xy = jingwai_step["coord"]
    nav_jingwai_to_entry = jingwai_step["navigate"]

    tap_transfer_2 = _tap_system_transfer_once()
    if tap_transfer_2 is None:
        return {
            "ok": False,
            "reason": "transfer_not_found_2",
            "fly": fly,
            "navigate_jingwai_to_entry": nav_jingwai_to_entry,
        }

    nav_in_target = vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    return {
        "ok": True,
        "strategy": strategy,
        "coord": target_coord,
        "fly_to_zhuziguo": fly,
        "tap_transfer_1": tap_transfer_1,
        "jingwai_entry_coord": jingwai_xy,
        "navigate_jingwai_to_entry": nav_jingwai_to_entry,
        "tap_transfer_2": tap_transfer_2,
        "navigate_in_target": nav_in_target,
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

    entry_step = _navigate_to_config_coord(entry_coord_text)
    entry_xy = entry_step["coord"]
    nav_to_entry = entry_step["navigate"]

    tap_transfer = _tap_system_transfer_once()
    if tap_transfer is None:
        return {
            "ok": False,
            "reason": "transfer_not_found",
            "fly": fly,
            "navigate_to_entry": nav_to_entry,
        }

    nav_in_target = vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    return {
        "ok": True,
        "strategy": strategy,
        "coord": target_coord,
        "fly": fly,
        "entry_coord": entry_xy,
        "navigate_to_entry": nav_to_entry,
        "tap_transfer": tap_transfer,
        "navigate_in_target": nav_in_target,
    }


def _route_via_direct_fly(destination: str, target_coord: Tuple[int, int]) -> Dict[str, Any]:
    fly = fly_to(destination)
    if not bool(fly.get("ok")):
        return {"ok": False, "reason": f"fly_to_{destination}_failed", "fly": fly}

    nav_in_target = vision_bot.navigate_to_coord(x=int(target_coord[0]), y=int(target_coord[1]))
    return {
        "ok": True,
        "strategy": "fly_and_navigate",
        "destination": destination,
        "coord": target_coord,
        "fly": fly,
        "navigate_in_target": nav_in_target,
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

    tap_menu = operator_util.tap_template(botconfig.ANDROID_TPL_MENU_DAOJU, threshold=botconfig.ANDROID_THR_MENU_DAOJU)
    tap_feixingfu = operator_util.tap_template(botconfig.ANDROID_TPL_PROP_FEIXINGFU, threshold=botconfig.ANDROID_THR_PROP_FEIXINGFU)
    tap_use = operator_util.tap_template(botconfig.ANDROID_TPL_PROP_USE, threshold=botconfig.ANDROID_THR_PROP_USE)
    tap_map = operator_util.tap_template(map_tpl, threshold=botconfig.ANDROID_THR_FEIXINGFU_MAP)
    tap_close = operator_util.try_tap(botconfig.ANDROID_TPL_DAOJU_CLOSE, threshold=botconfig.ANDROID_THR_DAOJU_CLOSE)
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
    routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_SHITUO, coord, strategy="shituo")
    if not bool(routed.get("ok")):
        return routed
    routed["jingwai_to_shituo"] = routed.pop("jingwai_entry_coord")
    routed["navigate_jingwai_to_shituo_entry"] = routed.pop("navigate_jingwai_to_entry")
    routed["navigate_in_shituo_to_target"] = routed.pop("navigate_in_target")
    return routed


def route_to_mowang(coord: Tuple[int, int]) -> Dict[str, Any]:
    routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_MOWANG, coord, strategy="mowang")
    if not bool(routed.get("ok")):
        return routed
    routed["jingwai_to_mowang"] = routed.pop("jingwai_entry_coord")
    routed["navigate_jingwai_to_mowang_entry"] = routed.pop("navigate_jingwai_to_entry")
    routed["navigate_in_mowang_to_target"] = routed.pop("navigate_in_target")
    return routed

def route_to_huasheng(coord: Tuple[int, int]) -> Dict[str, Any]:
    routed = _route_via_single_transfer(
        "长安城",
        botconfig.CHANGAN_TO_HUANSHENG,
        coord,
        strategy="huasheng",
    )
    if not bool(routed.get("ok")):
        return routed
    routed["fly_to_changan"] = routed.pop("fly")
    routed["changan_to_huansheng"] = routed.pop("entry_coord")
    routed["navigate_changan_to_huasheng_entry"] = routed.pop("navigate_to_entry")
    routed["tap_transfer_to_huasheng"] = routed.pop("tap_transfer")
    routed["navigate_in_huasheng_to_target"] = routed.pop("navigate_in_target")
    return routed

# def route_to_putuo(coord: Tuple[int, int]) -> Dict[str, Any]:
#     routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_PUTUO, coord, strategy="putuo")
#     if not bool(routed.get("ok")):
#         return routed
#     routed["jingwai_to_putuo"] = routed.pop("jingwai_entry_coord")
#     routed["navigate_jingwai_to_putuo_entry"] = routed.pop("navigate_jingwai_to_entry")
#     routed["navigate_in_putuo_to_target"] = routed.pop("navigate_in_target")
#     return routed

# def route_to_difu(coord: Tuple[int, int]) -> Dict[str, Any]:
#     routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_DIFU, coord, strategy="difu")
#     if not bool(routed.get("ok")):
#         return routed
#     routed["jingwai_to_difu"] = routed.pop("jingwai_entry_coord")
#     routed["navigate_jingwai_to_difu_entry"] = routed.pop("navigate_jingwai_to_entry")
#     routed["navigate_in_difu_to_target"] = routed.pop("navigate_in_target")
#     return routed

# def route_to_wuzhuang(coord: Tuple[int, int]) -> Dict[str, Any]:
#     routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_WUHUANG, coord, strategy="wuzhuang")
#     if not bool(routed.get("ok")):
#         return routed
#     routed["jingwai_to_wuzhuang"] = routed.pop("jingwai_entry_coord")
#     routed["navigate_jingwai_to_wuzhuang_entry"] = routed.pop("navigate_jingwai_to_entry")
#     routed["navigate_in_wuzhuang_to_target"] = routed.pop("navigate_in_target")
#     return routed

# def route_to_pansi(coord: Tuple[int, int]) -> Dict[str, Any]:
#     routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_PANSI, coord, strategy="pansi")
#     if not bool(routed.get("ok")):
#         return routed
#     routed["jingwai_to_pansi"] = routed.pop("jingwai_entry_coord")
#     routed["navigate_jingwai_to_pansi_entry"] = routed.pop("navigate_jingwai_to_entry")
#     routed["navigate_in_pansi_to_target"] = routed.pop("navigate_in_target")
#     return routed

def route_to_donghaiwan(coord: Tuple[int, int]) -> Dict[str, Any]:
    routed = _route_via_single_transfer(
        "建邺城",
        botconfig.JIANYE_TO_DONGHAIWAN,
        coord,
        strategy="donghaiwan",
    )
    if not bool(routed.get("ok")):
        return routed
    routed["fly_to_jianye"] = routed.pop("fly")
    routed["jianye_to_donghaiwan"] = routed.pop("entry_coord")
    routed["navigate_jianye_to_donghaiwan_entry"] = routed.pop("navigate_to_entry")
    routed["tap_transfer_to_donghaiwan"] = routed.pop("tap_transfer")
    routed["navigate_in_donghaiwan_to_target"] = routed.pop("navigate_in_target")
    return routed

def route_to_nver(coord: Tuple[int, int]) -> Dict[str, Any]:
    routed = _route_via_single_transfer(
        "傲来国",
        botconfig.AOLAI_TO_NVER,
        coord,
        strategy="nver",
    )
    if not bool(routed.get("ok")):
        return routed
    routed["fly_to_aolai"] = routed.pop("fly")
    routed["aolai_to_nver"] = routed.pop("entry_coord")
    routed["navigate_aolai_to_nver_entry"] = routed.pop("navigate_to_entry")
    routed["tap_transfer_to_nver"] = routed.pop("tap_transfer")
    routed["navigate_in_nver_to_target"] = routed.pop("navigate_in_target")
    return routed

# def route_to_tiangong(coord: Tuple[int, int]) -> Dict[str, Any]:
#     routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_TIANGONG, coord, strategy="tiangong")
#     if not bool(routed.get("ok")):
#         return routed
#     routed["jingwai_to_tiangong"] = routed.pop("jingwai_entry_coord")
#     routed["navigate_jingwai_to_tiangong_entry"] = routed.pop("navigate_jingwai_to_entry")
#     routed["navigate_in_tiangong_to_target"] = routed.pop("navigate_in_target")
#     return routed

# def route_to_fangcun(coord: Tuple[int, int]) -> Dict[str, Any]:
#     routed = _route_via_jingwai_transfer(botconfig.JINGWAI_TO_FANGCUN, coord, strategy="fangcun")
#     if not bool(routed.get("ok")):
#         return routed
#     routed["jingwai_to_fangcun"] = routed.pop("jingwai_entry_coord")
#     routed["navigate_jingwai_to_fangcun_entry"] = routed.pop("navigate_jingwai_to_entry")
#     routed["navigate_in_fangcun_to_target"] = routed.pop("navigate_in_target")
#     return routed


def route_by_map(map_name: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
    dest = str(map_name or "").strip()
    if dest in ("狮驼岭"):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return route_to_shituo((int(coord[0]), int(coord[1])))

    if dest in ("魔王寨"):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return route_to_mowang((int(coord[0]), int(coord[1])))

    if dest in ("化生寺",):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return route_to_huasheng((int(coord[0]), int(coord[1])))

    if dest in ("东海湾",):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return route_to_donghaiwan((int(coord[0]), int(coord[1])))

    if dest in ("女儿村",):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return route_to_nver((int(coord[0]), int(coord[1])))

    if dest in ("建邺城", "长寿村", "朱紫国", "傲来国", "宝象国", "长安城","西梁女国"):
        if coord is None:
            return {"ok": False, "reason": "missing_target_coord", "map_name": map_name, "coord": coord}
        return _route_via_direct_fly(dest, (int(coord[0]), int(coord[1])))

    return {"ok": False, "reason": "not_implemented", "map_name": map_name, "coord": coord}
