import time
from typing import Any, Dict, Optional, Sequence, Tuple

import botconfig
import adb_util


def _parse_xy(text: str) -> Optional[Tuple[int, int]]:
    s = str(text or "").strip()
    if not s:
        return None
    s = s.replace("，", ",")
    parts = [p.strip() for p in s.replace(" ", ",").split(",") if p.strip()]
    if len(parts) >= 2:
        try:
            return int(parts[0]), int(parts[1])
        except Exception:
            return None
    digits = []
    cur = ""
    for ch in s:
        if ch.isdigit():
            cur += ch
        else:
            if cur:
                digits.append(cur)
                cur = ""
    if cur:
        digits.append(cur)
    if len(digits) >= 2:
        try:
            return int(digits[0]), int(digits[1])
        except Exception:
            return None
    return None


def load_word_puzzle_points_from_env() -> Dict[int, Tuple[int, int]]:
    return botconfig.word_puzzle_points_from_env()


def click_word_puzzle_by_indices(answer_indices: Sequence[int], sleep_s: Optional[float] = None) -> Dict[str, Any]:
    indices = []
    for x in answer_indices:
        try:
            indices.append(int(x))
        except Exception:
            continue
    indices = indices[:4]

    pts = load_word_puzzle_points_from_env()
    missing = [i for i in (1, 2, 3, 4) if i not in pts]
    if missing:
        raise RuntimeError(f"缺少点字坐标配置: {missing}，请设置 {botconfig.WORD_PUZZLE_POINTS_DOC}")

    if sleep_s is None:
        sleep_s = botconfig.ANDROID_STEP_SLEEP_S_WORD_PUZZLE

    taps = []
    for idx in indices:
        if idx not in pts:
            continue
        x, y = pts[idx]
        adb_util.tap(x, y)
        taps.append({"index": idx, "xy": (x, y)})
        if float(sleep_s) > 0:
            time.sleep(float(sleep_s))
    return {"ok": True, "answer_indices": indices, "taps": taps}
