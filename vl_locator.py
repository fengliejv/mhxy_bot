import json
from typing import Any, Dict, Optional, Tuple, Union

import numpy as np

import siliflow_client


def locate_text_center(
    image: Union[np.ndarray, str, bytes],
    query: str,
    roi: Optional[Tuple[int, int, int, int]] = None,
) -> Optional[Dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return None

    img = image
    offset_x = 0
    offset_y = 0
    if isinstance(image, np.ndarray) and roi is not None:
        x1, y1, x2, y2 = roi
        h, w = image.shape[:2]
        x1 = max(0, min(int(x1), w - 1))
        x2 = max(x1 + 1, min(int(x2), w))
        y1 = max(0, min(int(y1), h - 1))
        y2 = max(y1 + 1, min(int(y2), h))
        img = image[y1:y2, x1:x2].copy()
        offset_x = x1
        offset_y = y1

    schema = {
        "type": "object",
        "properties": {
            "found": {"type": "boolean"},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "confidence": {"type": "number"},
            "matched_text": {"type": "string"},
        },
        "required": ["found"],
    }

    prompt = (
        "在图片中找到与查询词匹配的文字位置（完全一致优先，其次允许部分包含）。"
        "如果找到，返回该文字区域中心点坐标 (x,y)，坐标以图片左上角为(0,0)。"
        "如果没找到，found=false。\n\n"
        f"查询词：{q}"
    )
    resp = siliflow_client.siliconflow_qwen_structured(img, prompt=prompt, schema=schema)
    parsed = resp.get("parsed")
    if not isinstance(parsed, dict):
        return None
    if not parsed.get("found"):
        return None
    try:
        x = int(parsed.get("x"))
        y = int(parsed.get("y"))
    except Exception:
        return None
    return {
        "x": x + offset_x,
        "y": y + offset_y,
        "confidence": float(parsed.get("confidence") or 0.0),
        "matched_text": str(parsed.get("matched_text") or ""),
        "raw": json.dumps(parsed, ensure_ascii=False),
    }

