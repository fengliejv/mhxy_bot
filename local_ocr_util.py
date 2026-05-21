import argparse
import io
import os
import re
import time
from typing import Any, Dict, Optional, Sequence, Tuple

from PIL import Image, ImageFilter, ImageOps

import sys_util


_OCR_ENGINE = None


def _load_image(image: Any) -> Image.Image:
    if isinstance(image, Image.Image):
        return image.convert("RGB")
    path = os.path.expanduser(str(image))
    with Image.open(path) as img:
        return img.convert("RGB")


def _to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _image_to_png_bytes(image: Any) -> bytes:
    if isinstance(image, Image.Image):
        return _to_png_bytes(image.convert("RGB"))
    if isinstance(image, str):
        path = os.path.expanduser(str(image))
        with Image.open(path) as img:
            return _to_png_bytes(img.convert("RGB"))
    if isinstance(image, (bytes, bytearray, memoryview)):
        return bytes(image)
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
        return bytes(buf)
    raise RuntimeError(f"不支持的图片输入类型: {type(image)!r}")


def _parse_coord_text(text: str) -> Optional[Tuple[int, int]]:
    s = str(text or "").strip()
    if not s:
        return None
    m = re.search(r"(\d{1,3})\s*[,，]\s*(\d{1,3})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    nums = re.findall(r"\d+", s)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1])
    return None


def _white_text_mask(img: Image.Image) -> Image.Image:
    rgb = img.convert("RGB")
    w, h = rgb.size
    src = rgb.load()
    mask = Image.new("L", (w, h), 0)
    dst = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = src[x, y]
            mx = max(r, g, b)
            mn = min(r, g, b)
            if mx >= 145 and (mx - mn) <= 105:
                dst[x, y] = 255
    mask = mask.filter(ImageFilter.MinFilter(3))
    mask = mask.filter(ImageFilter.MaxFilter(3))
    return mask


def _tight_crop_by_mask(img: Image.Image, mask: Image.Image, pad: int = 8) -> Image.Image:
    bbox = mask.getbbox()
    if bbox is None:
        return img
    x1, y1, x2, y2 = bbox
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(img.size[0], x2 + pad)
    y2 = min(img.size[1], y2 + pad)
    return img.crop((x1, y1, x2, y2))


def _build_variant(img: Image.Image) -> Tuple[str, Image.Image]:
    upscaled = img.resize((img.size[0] * 4, img.size[1] * 4), resample=Image.Resampling.LANCZOS)
    mask = _white_text_mask(upscaled)
    cropped = _tight_crop_by_mask(upscaled, mask, pad=12)
    cropped = ImageOps.autocontrast(cropped)
    return "upscaled_crop", cropped


def _get_ocr_engine():
    global _OCR_ENGINE
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE
    try:
        from rapidocr_onnxruntime import RapidOCR
    except Exception as e:
        raise RuntimeError("缺少 rapidocr_onnxruntime，请先安装: pip install rapidocr_onnxruntime onnxruntime") from e
    _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def run_local_ocr(
    image: Any,
    *,
    use_det: bool,
    use_cls: bool = False,
    use_rec: bool = True,
    log_prefix: str = "[CoordOCRUtil]",
) -> Dict[str, Any]:
    engine = _get_ocr_engine()
    image_png = _image_to_png_bytes(image)
    start = time.perf_counter()
    result, elapse = engine(image_png, use_det=use_det, use_cls=use_cls, use_rec=use_rec)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    print(f"{log_prefix} local_rapidocr elapsed_ms={elapsed_ms:.1f}")
    print(f"{log_prefix} engine_elapse={elapse}")
    return {"result": result, "elapsed_ms": elapsed_ms, "engine_elapse": elapse}


def flatten_ocr_text(result: Any) -> str:
    if not result:
        return ""
    parts = []
    for item in result:
        if not isinstance(item, Sequence) or len(item) < 1:
            continue
        if isinstance(item[0], str):
            parts.append(str(item[0]))
            continue
        if len(item) >= 2 and isinstance(item[1], str):
            parts.append(str(item[1]))
    return "".join(parts).strip()


def _ocr_coord_local(image_png: bytes, variant_name: str) -> Dict[str, Any]:
    resp = run_local_ocr(image_png, use_det=False, use_cls=False, use_rec=True)
    raw_text = flatten_ocr_text(resp.get("result"))
    coord = _parse_coord_text(raw_text)
    print(f"[CoordOCRUtil] variant={variant_name} raw_text={raw_text!r} coord={coord}")
    return {
        "variant": variant_name,
        "coord": coord,
    }


def detect_coord(image: Any, save_debug: bool = False) -> Dict[str, Any]:
    img = _load_image(image)
    name, variant = _build_variant(img)
    if save_debug:
        sys_util.save_debug_image(variant, f"coord_ocr_{name}")
    result = _ocr_coord_local(_to_png_bytes(variant), variant_name=name)
    return {
        "ok": result["coord"] is not None,
        "coord": result["coord"],
        "variant": name,
    }


def main() -> None:
    result = detect_coord('assets/3.第三册桥梁涵洞第1合同_p82-83.png', save_debug=True)
    print(result)


if __name__ == "__main__":
    main()
