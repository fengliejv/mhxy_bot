import os
import threading
from typing import Optional, Sequence

_lock = threading.Lock()
_dotenv_loaded = False
_dotenv_path = ".env"

ADB_PATH = "adb"

ANDROID_MATCH_THRESHOLD = 0.8
ANDROID_STEP_SLEEP_S = 0.4
ANDROID_STEP_SLEEP_S_WORD_PUZZLE = 0.25

ANDROID_THR_MAP_BUTTON = 0.6
ANDROID_THR_MAP_X = ANDROID_MATCH_THRESHOLD
ANDROID_THR_MAP_Y = ANDROID_MATCH_THRESHOLD
ANDROID_THR_MAP_GO = ANDROID_MATCH_THRESHOLD

ANDROID_ADB_IME_ID = "com.android.adbkeyboard/.AdbIME"
ANDROID_SOGOU_IME_ID = "com.sohu.inputmethod.sogou.xiaomi/.SogouIME"

ANDROID_ARRIVAL_MAX_WAIT_S = 60.0
ANDROID_ARRIVAL_CHECK_INTERVAL_S = 1.0
ANDROID_ARRIVAL_STABLE_COUNT = 2

ANDROID_THR_MENU_DAOJU = ANDROID_MATCH_THRESHOLD
ANDROID_THR_PROP_FEIXINGFU = ANDROID_MATCH_THRESHOLD
ANDROID_THR_PROP_USE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_FEIXINGFU_MAP = ANDROID_MATCH_THRESHOLD
ANDROID_THR_DAOJU_CLOSE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_TRANSFER = ANDROID_MATCH_THRESHOLD
ANDROID_TRANSFER_RETRY = 10
ANDROID_TRANSFER_RETRY_SLEEP_S = ANDROID_STEP_SLEEP_S

ANDROID_THR_SYSTEM_CLOSE_GUIDE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_CLOSE_TASK = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_HIDE_DIALOG = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_AUTO_ATTACK_SHRINK = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_EXPAND = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_HIDE_UI_DISABLE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_HIDE_PLAYER_DISABLE = ANDROID_MATCH_THRESHOLD
ANDROID_THR_SYSTEM_BACK = ANDROID_MATCH_THRESHOLD

ANDROID_THR_PROP_CHANGAN_FLAG = ANDROID_MATCH_THRESHOLD
ANDROID_THR_MAP_TELEPORT_POINT = ANDROID_MATCH_THRESHOLD
ANDROID_TELEPORT_TARGET_X = 1640
ANDROID_TELEPORT_TARGET_Y = 500

ANDROID_THR_BAOTU_RECEIVE_TASK = ANDROID_MATCH_THRESHOLD
ANDROID_THR_NPC_XIAOER = 0.4
ANDROID_THR_CHANGAN_HOTEL_DOOR = ANDROID_MATCH_THRESHOLD

MHXY_MAP_ROI = ""
ANDROID_COORD_ROI = ""

ANDROID_TPL_MAP_BUTTON = "assets/android/map/map_button.jpg"
ANDROID_TPL_MAP_BUTTON_2 = "assets/android/map/map_button2.png"
ANDROID_TPL_MAP_SEARCH_ICON = "assets/android/map/map_search_icon.png"
ANDROID_TPL_MAP_INPUT_ICON = "assets/android/map/map_input_icon.png"
ANDROID_TPL_MAP_GO = "assets/android/map/map_go.jpg"
ANDROID_TPL_MAP_EXIT = "assets/android/map/map_exit.jpg"
ANDROID_TPL_MAP_DIANXIAOER = "assets/android/map/map_dianxiaoer.png"
ANDROID_TPL_MAP_ON_THE_WAY = "assets/android/map/map_on_the_way.png"
ANDROID_TPL_MENU_DAOJU = "assets/android/memu/daoju.jpg"
ANDROID_TPL_PROP_CHANGAN_FLAG = "assets/android/daoju/changandaobiaoqi.png"
ANDROID_TPL_PROP_USE = "assets/android/daoju/jiemian/shiyong.png"
ANDROID_TPL_MAP_TELEPORT_POINT = "assets/android/map/daobiaoqiditu/chuansongdian.png"
ANDROID_TPL_BAOTU_RECEIVE_TASK = "assets/android/baotu/tingtingwufang.png"
ANDROID_TPL_CHANGAN_HOTEL_DOOR = "assets/android/changancheng/jiudianmenkou.png"
ANDROID_TPL_SYSTEM_CLOSE_GUIDE = "assets/android/system/guanbizhiyin.png"
ANDROID_TPL_SYSTEM_CLOSE_TASK = "assets/android/system/close_task.jpg"
ANDROID_TPL_SYSTEM_HIDE_DIALOG = "assets/android/system/yincangduihua.png"
ANDROID_TPL_SYSTEM_AUTO_ATTACK_SHRINK = "assets/android/system/zidonggongjisuoxiao.png"
ANDROID_TPL_SYSTEM_EXPAND = "assets/android/system/expand.jpg"
ANDROID_TPL_SYSTEM_HIDE_UI_DISABLE = "assets/android/system/yincangjiemian_disable.png"
ANDROID_TPL_SYSTEM_HIDE_PLAYER_DISABLE = "assets/android/system/yincangwanjia_disable.png"
ANDROID_TPL_SYSTEM_BACK = "assets/android/system/back.png"
ANDROID_TPL_NPC_DIANXIAOER_1 = "assets/android/npc/dianxiaoer1.png"
ANDROID_TPL_NPC_DIANXIAOER_2 = "assets/android/npc/dianxiaoer2.png"
ANDROID_TPL_NPC_DIANXIAOER_3 = "assets/android/npc/dianxiaoer3.png"

MINERU_CMD = ""

SILICONFLOW_API_KEY = ""
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_OCR_MODEL = "PaddlePaddle/PaddleOCR-VL-1.5"
SILICONFLOW_QWEN_MODEL = "Qwen/Qwen3.6-VL-Plus"


def init(dotenv_path: str = ".env") -> None:
    global _dotenv_loaded, _dotenv_path
    p = str(dotenv_path or ".env").strip() or ".env"
    if _dotenv_loaded and p == _dotenv_path:
        return
    with _lock:
        if _dotenv_loaded and p == _dotenv_path:
            return
        _dotenv_path = p
        _load_dotenv(p)
        _dotenv_loaded = True


def _load_dotenv(path: str) -> None:
    if not path:
        return
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def env_str(key: str, default: str = "") -> str:
    init()
    v = os.getenv(str(key), "")
    s = str(v or "").strip()
    if s:
        return s
    return str(default or "")


def env_optional_str(key: str) -> Optional[str]:
    init()
    s = str(os.getenv(str(key), "") or "").strip()
    return s or None


def env_str_first(keys: Sequence[str], default: str = "") -> str:
    for k in keys:
        v = env_str(str(k), "")
        if v:
            return v
    return str(default or "")


def env_int(key: str, default: int) -> int:
    s = env_str(key, "")
    if not s:
        return int(default)
    return int(s)


def env_float(key: str, default: float) -> float:
    s = env_str(key, "")
    if not s:
        return float(default)
    return float(s)


def env_bool(key: str, default: bool = False) -> bool:
    s = env_str(key, "")
    if not s:
        return bool(default)
    v = s.strip().lower()
    if v in ("1", "true", "yes", "y", "on"):
        return True
    if v in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def require_str(key: str) -> str:
    v = env_str(key, "")
    if not v:
        raise RuntimeError(f"缺少 {key}，请在环境变量或 .env 中配置")
    return v


def is_debug() -> bool:
    return env_bool("DEBUG", default=False)


def environ_copy() -> dict:
    init()
    return dict(os.environ)
