from typing import Tuple


def parse_roi(roi_text: str, env_name: str) -> Tuple[int, int, int, int]:
    parts = [x.strip() for x in str(roi_text or "").split(",")]
    if len(parts) != 4:
        raise RuntimeError(f"{env_name} 格式错误，期望 x1,y1,x2,y2")
    x1, y1, x2, y2 = [int(v) for v in parts]
    if x1 < 0 or y1 < 0:
        raise RuntimeError(f"{env_name} 数值无效，要求 x1>=0,y1>=0")
    if x2 <= x1 or y2 <= y1:
        raise RuntimeError(f"{env_name} 数值无效，要求 x2>x1,y2>y1")
    return x1, y1, x2, y2
