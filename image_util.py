import os
import sys
import datetime
import argparse

import cv2


def crop_center_region_to_assets(image_path: str, x: int, y: int, m: int, n: int) -> str:
    if not image_path:
        raise ValueError("image_path 不能为空")
    if m <= 0 or n <= 0:
        raise ValueError("m/n 必须为正数")

    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError("无法读取图片: {}".format(image_path))

    h, w = img.shape[:2]
    cx = int(x)
    cy = int(y)
    half_w = int(m) // 2
    half_h = int(n) // 2

    x1 = cx - half_w
    y1 = cy - half_h
    x2 = x1 + int(m)
    y2 = y1 + int(n)

    x1 = 0 if x1 < 0 else (w if x1 > w else x1)
    y1 = 0 if y1 < 0 else (h if y1 > h else y1)
    x2 = 0 if x2 < 0 else (w if x2 > w else x2)
    y2 = 0 if y2 < 0 else (h if y2 > h else y2)

    if x2 <= x1 or y2 <= y1:
        raise RuntimeError("裁剪区域无效：图片尺寸=({},{}), 裁剪=({}, {}, {}, {})".format(w, h, x1, y1, x2, y2))

    cropped = img[y1:y2, x1:x2]

    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(assets_dir, exist_ok=True)

    base = os.path.splitext(os.path.basename(image_path))[0]
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = "{}_crop_c{}_{}_{}x{}_{}.png".format(base, cx, cy, m, n, ts)
    out_path = os.path.join(assets_dir, out_name)

    ok = cv2.imwrite(out_path, cropped)
    if not ok:
        raise RuntimeError("保存失败: {}".format(out_path))
    return out_path


def main(argv=None) -> int:
    # parser = argparse.ArgumentParser()
    # parser.add_argument("image_path", help="输入图片路径")
    # parser.add_argument("x", type=int, help="中心点 x（像素）")
    # parser.add_argument("y", type=int, help="中心点 y（像素）")
    # parser.add_argument("m", type=int, help="裁剪宽度 m（像素）")
    # parser.add_argument("n", type=int, help="裁剪高度 n（像素）")
    # args = parser.parse_args(argv)

    out_path = crop_center_region_to_assets("assets/test.png", 575, 345, 80, 80)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
