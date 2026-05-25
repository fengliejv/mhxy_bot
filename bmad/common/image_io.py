import io
import os
from typing import Any


def to_png_bytes(image: Any) -> bytes:
    if isinstance(image, (bytes, bytearray, memoryview)):
        return bytes(image)

    try:
        from PIL import Image  # type: ignore
    except Exception:
        Image = None

    if Image is not None:
        if isinstance(image, Image.Image):
            buf = io.BytesIO()
            image.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        if isinstance(image, str):
            path = os.path.expanduser(str(image))
            with Image.open(path) as img:
                buf = io.BytesIO()
                img.convert("RGB").save(buf, format="PNG")
                return buf.getvalue()

    if hasattr(image, "shape") and hasattr(image, "dtype"):
        import numpy as np  # type: ignore
        import cv2  # type: ignore

        arr = np.asarray(image)
        if not arr.flags["C_CONTIGUOUS"]:
            arr = np.ascontiguousarray(arr)
        ok, buf = cv2.imencode(".png", arr)
        if not ok:
            raise RuntimeError("图片编码失败（cv2.imencode .png）")
        return bytes(buf)

    if isinstance(image, str):
        import cv2  # type: ignore

        img = cv2.imread(image)
        if img is None:
            raise RuntimeError(f"读取图片失败: {image}")
        return to_png_bytes(img)

    raise RuntimeError(f"不支持的图片输入类型: {type(image)!r}")


def to_bgr(image: Any):
    if hasattr(image, "shape") and hasattr(image, "dtype"):
        import numpy as np  # type: ignore

        return np.asarray(image).copy()
    if isinstance(image, str):
        import cv2  # type: ignore

        img = cv2.imread(image)
        if img is None:
            raise RuntimeError(f"读取图片失败: {image}")
        return img
    if isinstance(image, (bytes, bytearray, memoryview)):
        import numpy as np  # type: ignore
        import cv2  # type: ignore

        arr = np.frombuffer(bytes(image), dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("图片解码失败")
        return img
    raise RuntimeError(f"不支持的图片输入类型: {type(image)!r}")

