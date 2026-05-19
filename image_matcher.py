#!/usr/bin/env python3
"""
图像模板匹配脚本
在图A中检测图B对应的元素并标记出来
"""

import cv2
import numpy as np
import argparse
import os
from typing import List, Tuple, Optional, Union
import datetime
import os

import sys_util


_METHODS = {
    "auto": None,
    "ccoeff": cv2.TM_CCOEFF,
    "ccoeff_normed": cv2.TM_CCOEFF_NORMED,
    "ccorr": cv2.TM_CCORR,
    "ccorr_normed": cv2.TM_CCORR_NORMED,
    "sqdiff": cv2.TM_SQDIFF,
    "sqdiff_normed": cv2.TM_SQDIFF_NORMED,
}


def load_image(source: Union[str, np.ndarray, bytes, bytearray, memoryview]) -> Optional[np.ndarray]:
    if isinstance(source, np.ndarray):
        return source
    if isinstance(source, (bytes, bytearray, memoryview)):
        buf = np.frombuffer(bytes(source), dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if img is None:
            print("错误: 无法解码图片字节")
            return None
        return img

    path = str(source)
    if not os.path.exists(path):
        print(f"错误: 图片不存在 - {path}")
        return None
    img = cv2.imread(path)
    if img is None:
        print(f"错误: 无法读取图片 - {path}")
        return None
    return img


def _resolve_method(method_name: str) -> int:
    name = str(method_name or "auto").strip().lower()
    if name == "auto":
        return cv2.TM_CCOEFF_NORMED
    return _METHODS.get(name, cv2.TM_CCOEFF_NORMED)


def _match_template_best(source: np.ndarray, template: np.ndarray, method_name: str = "auto") -> Tuple[float, Tuple[int, int]]:
    method = _resolve_method(method_name)
    result = cv2.matchTemplate(source, template, method)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
        confidence = 1 - min_val
        top_left = min_loc
    else:
        confidence = max_val
        top_left = max_loc
    return float(confidence), (int(top_left[0]), int(top_left[1]))


def _non_max_suppression(
    locations: List[Tuple[Tuple[int, int], float]], w: int, h: int, overlap_thresh: float = 0.3
) -> List[Tuple[Tuple[int, int], float]]:
    if len(locations) == 0:
        return []

    locations = sorted(locations, key=lambda x: x[1], reverse=True)
    pick = []
    while len(locations) > 0:
        current = locations[0]
        pick.append(current)
        locations = locations[1:]

        remaining = []
        for loc in locations:
            pt, conf = loc
            xx1 = max(current[0][0], pt[0])
            yy1 = max(current[0][1], pt[1])
            xx2 = min(current[0][0] + w, pt[0] + w)
            yy2 = min(current[0][1] + h, pt[1] + h)

            w_intersect = max(0, xx2 - xx1)
            h_intersect = max(0, yy2 - yy1)
            overlap = (w_intersect * h_intersect) / (w * h)

            if overlap <= overlap_thresh:
                remaining.append(loc)

        locations = remaining

    return pick


def _match_all_templates(
    source: np.ndarray, template: np.ndarray, threshold: float, method_name: str = "auto"
) -> List[Tuple[Tuple[int, int], float]]:
    method = _resolve_method(method_name)
    result = cv2.matchTemplate(source, template, method)

    if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
        threshold_val = 1 - float(threshold)
        locs = np.where(result <= threshold_val)
    else:
        threshold_val = float(threshold)
        locs = np.where(result >= threshold_val)

    locations = []
    for pt in zip(*locs[::-1]):
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1 - float(result[pt[1], pt[0]])
        else:
            confidence = float(result[pt[1], pt[0]])
        locations.append(((int(pt[0]), int(pt[1])), float(confidence)))

    locations = _non_max_suppression(locations, template.shape[1], template.shape[0])
    return locations


def draw_matches(source: np.ndarray, template: np.ndarray, locations: List[Tuple[Tuple[int, int], float]]) -> np.ndarray:
    result = source.copy()
    h, w = template.shape[:2]
    for i, (top_left, confidence) in enumerate(locations):
        bottom_right = (top_left[0] + w, top_left[1] + h)
        cv2.rectangle(result, top_left, bottom_right, (0, 255, 0), 2)
        label = f"Match {i+1}: {confidence:.2f}"
        label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        label_top = max(top_left[1] - label_size[1] - 5, 0)
        label_bottom = label_top + label_size[1] + baseline
        cv2.rectangle(
            result,
            (top_left[0], label_top),
            (top_left[0] + label_size[0], label_bottom),
            (0, 255, 0),
            -1,
        )
        cv2.putText(
            result,
            label,
            (top_left[0], label_top + label_size[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
        )

    return result
    

#对外暴露的函数接口，供其他模块调用
def match_template(
    source_path: Union[str, np.ndarray, bytes, bytearray, memoryview],
    template_path: Union[str, np.ndarray, bytes, bytearray, memoryview],
    output_path: Optional[str] = None,
    threshold: float = 0.8,
    find_all: bool = True,
    show_result: bool = False,
) -> Tuple[bool, Optional[np.ndarray], List[Tuple[Tuple[int, int], float]]]:
    """
    图像模板匹配函数接口
    
    参数:
        source_path: 源图片（路径 / numpy.ndarray / 图片字节）
        template_path: 模板图片（路径 / numpy.ndarray / 图片字节）
        output_path: 输出图片路径或目录，为 None 时不保存
        threshold: 匹配阈值 (0-1)
        find_all: 是否查找所有匹配项
        show_result: 是否显示结果窗口
    
    返回:
        success: 是否成功匹配
        result_image: 标记后的结果图像，失败时为 None
        locations: 匹配位置列表，每个元素为 ((x, y), confidence)
    """
    source = load_image(source_path)
    if source is None:
        return False, None, []
    
    template = load_image(template_path)
    if template is None:
        return False, None, []
    
    # 4) 模板尺寸校验
    if template.shape[0] > source.shape[0] or template.shape[1] > source.shape[1]:
        print("错误: 模板图片尺寸大于源图片")
        return False, None, []
    
    if find_all:
        locations = _match_all_templates(source, template, threshold=threshold, method_name="ccoeff_normed")
    else:
        confidence, top_left = _match_template_best(source, template, method_name="ccoeff_normed")
        if confidence >= threshold:
            locations = [(top_left, confidence)]
        else:
            locations = []
    
    # 6) 无匹配直接返回失败
    if len(locations) == 0:
        return False, None, []
    
    result_image = draw_matches(source, template, locations)
    
    if output_path is not None:
        out_path = output_path
        if os.path.isdir(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(output_path, f"matched_{ts}.png")
        cv2.imwrite(out_path, result_image)

    if show_result:
        try:
            cv2.imshow("Matched Result", result_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        except Exception:
            pass

    sys_util.save_debug_image(result_image, "detected"+template_path.split("/")[-1])
    # 10) 返回结果：是否成功、结果图、匹配列表
    return True, result_image, locations


def main():
    # 这里是脚本直接运行时的示例入口
    source_path = "debug_capture/20260519_232859_android_screencap.png"

    # 调用对外接口执行匹配
    success, _, locations = match_template(
        source_path,
        template_path="assets/android/map/feixingfuditu/changancheng.png",
        threshold=0.3,
        find_all=True,
        output_path="debug_capture",
        show_result=True,
    )
    # 打印匹配坐标信息（便于后续程序使用）
    print("匹配位置信息:", locations)
    if not success:
        print("\n匹配失败")


if __name__ == "__main__":
    # 直接运行该文件时执行 main()
    main()
