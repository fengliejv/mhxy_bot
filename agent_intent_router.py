import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Union

import sys_util


ImageInput = Union[str, bytes, bytearray, memoryview, Any]


@dataclass(frozen=True)
class BaotuParams:
    qiangdao_name: str
    location: str


@dataclass(frozen=True)
class WordPuzzleParams:
    answer_indices: List[int]


def _to_png_bytes(image: ImageInput) -> bytes:
    if isinstance(image, str):
        with open(os.path.expanduser(image), "rb") as f:
            return f.read()
    if hasattr(image, "shape") and hasattr(image, "dtype"):
        try:
            import numpy as np  # type: ignore
            import cv2  # type: ignore
        except Exception as e:
            raise RuntimeError("ndarray 图片输入需要 numpy+opencv-python") from e
        img = np.asarray(image)
        if not img.flags["C_CONTIGUOUS"]:
            img = np.ascontiguousarray(img)
        ok, buf = cv2.imencode(".png", img)
        if not ok:
            raise RuntimeError("图片编码失败（cv2.imencode .png）")
        return buf.tobytes()
    return bytes(image)

def _qwen_classify_and_extract(image: ImageInput) -> Dict[str, Any]:
    png = _to_png_bytes(image)
    # if os.getenv("DEBUG", "").strip().lower() in ("1", "true", "yes"):
    #     os.makedirs("debug_capture", exist_ok=True)
    #     with open(os.path.join("debug_capture", "agent_intent_input.png"), "wb") as f:
    #         f.write(png)
    schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "baotu": {
                "type": ["object", "null"],
                "properties": {
                    "qiangdao_name": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["qiangdao_name", "location"],
            },
            "word_puzzle": {
                "type": ["object", "null"],
                "properties": {
                    "answer_phrase": {"type": "string"},
                    "answer_indices": {"type": "array", "items": {"type": "integer"}, "minItems": 4, "maxItems": 4},
                },
                "required": ["answer_phrase", "answer_indices"],
            },
        },
        "required": ["category", "baotu", "word_puzzle"],
    }
    prompt = (
        "你在看一张截图。请判断图片属于以下哪一类：\n"
        "1) mhxy_baotu：梦幻西游“打宝图/打图/宝图任务/强盗”任务相关提示或任务信息\n"
        "2) word_puzzle：点字成词/点字成语游戏（下方有多个字，需要按顺序点出一个四字词语）\n"
        "3) other：其它\n\n"
        "输出 JSON。\n"
        "若 category=mhxy_baotu：提取 qiangdao_name(强盗/怪物名称) 与 location(地点/地图/坐标/场景)。\n"
        "若 category=word_puzzle：提取 answer_phrase(四字词语) 与 answer_indices(长度为4的整数数组，1-based，表示点击顺序对应下方字块的位置)。\n"
        "若无法确定字段则返回空字符串或 [ ] 并尽量给出你最可信的结果。\n"
    )
    try:
        import siliflow_client
    except Exception as e:
        raise RuntimeError("缺少 siliflow_client 或其依赖（numpy/opencv/pillow 等）") from e
    resp = siliflow_client.siliconflow_qwen_structured(png, prompt=prompt, schema=schema)
    print(f"qwen_classify_and_extract: {resp}")
    parsed = resp.get("parsed")
    if isinstance(parsed, dict):
        parsed["_raw"] = resp
        return parsed
    return {"category": "other", "baotu": None, "word_puzzle": None, "_raw": resp}


from agent_actions import baotu_task_stub, solve_word_puzzle_stub


def route_image_intent(image: ImageInput) -> Dict[str, Any]:
    r = _qwen_classify_and_extract(image)
    cat = str(r.get("category", "other") or "other").strip().lower()

    if cat in ("mhxy_baotu", "baotu", "mhxy"):
        b = r.get("baotu") or {}
        qiangdao_name = str(b.get("qiangdao_name", "") or "").strip()
        location = str(b.get("location", "") or "").strip()
        # params = BaotuParams(qiangdao_name=qiangdao_name, location=location)
        # called = baotu_task_stub(params.qiangdao_name, params.location)
        return {"category": "mhxy_baotu", "params": params.__dict__}

    if cat in ("word_puzzle", "puzzle", "idiom"):
        w = r.get("word_puzzle") or {}
        indices = w.get("answer_indices") or []
        if not isinstance(indices, list):
            indices = []
        indices2 = []
        for x in indices:
            try:
                indices2.append(int(x))
            except Exception:
                continue
        params = WordPuzzleParams(answer_indices=indices2[:4])
        called = solve_word_puzzle_stub(params.answer_indices)
        return {"category": "word_puzzle", "params": params.__dict__, "called": called, "raw": r.get("_raw")}

    return {"category": "other", "params": {}, "called": None, "raw": r.get("_raw")}


def main() -> None:
    sys_util.load_dotenv()
    out = route_image_intent("screen.png")
    # for k, v in out.items():
    #     print(f"{k}: {v}")


if __name__ == "__main__":
    main()
