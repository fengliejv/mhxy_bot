import time
from typing import Any, Dict, Optional, Tuple

import botconfig


class LocationStrategy:
    name = "unknown"

    def execute(self, bot: Any, destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return {"ok": False, "reason": "not_implemented", "strategy": self.name, "destination": destination, "coord": coord}


class Location_with_fly(LocationStrategy):
    name = "fly"

    def execute(self, bot: Any, destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
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

        thr_menu_daoju = botconfig.env_float("ANDROID_THR_MENU_DAOJU", botconfig.ANDROID_THR_MENU_DAOJU)
        thr_feixingfu = botconfig.env_float("ANDROID_THR_PROP_FEIXINGFU", botconfig.ANDROID_THR_PROP_FEIXINGFU)
        thr_use = botconfig.env_float("ANDROID_THR_PROP_USE", botconfig.ANDROID_THR_PROP_USE)
        thr_map = botconfig.env_float("ANDROID_THR_FEIXINGFU_MAP", botconfig.ANDROID_THR_FEIXINGFU_MAP)
        thr_close = botconfig.env_float("ANDROID_THR_DAOJU_CLOSE", botconfig.ANDROID_THR_DAOJU_CLOSE)

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

    def execute(self, bot: Any, destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        from vision_bot import navigate_to_coord

        fly = super().execute(bot, destination="朱紫国", coord=None)
        if not bool(fly.get("ok")):
            return {"ok": False, "reason": "fly_to_zhuziguo_failed", "strategy": self.name, "fly": fly}

        nav = navigate_to_coord(bot.adb, x=7, y=4)
        arrival = nav.get("arrival")

        thr_transfer = botconfig.env_float("ANDROID_THR_SYSTEM_TRANSFER", botconfig.ANDROID_THR_SYSTEM_TRANSFER)
        max_retry = botconfig.env_int("ANDROID_TRANSFER_RETRY", botconfig.ANDROID_TRANSFER_RETRY)
        retry_sleep_s = botconfig.env_float("ANDROID_TRANSFER_RETRY_SLEEP_S", botconfig.ANDROID_TRANSFER_RETRY_SLEEP_S)
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


class QiangdaoStrategyA(Location_with_fly):
    name = "A"

    def execute(self, bot: Any, destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return super().execute(bot, destination=destination, coord=coord)


class QiangdaoStrategyB(LocationStrategy):
    name = "B"

    def execute(self, bot: Any, destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return {"ok": False, "reason": "not_implemented", "strategy": self.name, "destination": destination, "coord": coord}


class QiangdaoStrategyC(LocationStrategy):
    name = "C"

    def execute(self, bot: Any, destination: str, coord: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        return {"ok": False, "reason": "not_implemented", "strategy": self.name, "destination": destination, "coord": coord}


def select_map_strategy(map_name: str) -> LocationStrategy:
    dest = str(map_name or "").strip()
    if dest in ("建邺城", "长寿村", "朱紫国", "傲来国", "宝象国", "女儿村", "西梁女国"):
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
