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




# 核心类：负责加载图片、执行模板匹配、筛除重复匹配、绘制标记结果
class TemplateMatcher:
    def __init__(self, method: str = "auto", threshold: float = 0.8):
        # 将可读的 method 名称映射到 OpenCV 的模板匹配枚举值
        self.methods = {
            "auto": None,
            "ccoeff": cv2.TM_CCOEFF,
            "ccoeff_normed": cv2.TM_CCOEFF_NORMED,
            "ccorr": cv2.TM_CCORR,
            "ccorr_normed": cv2.TM_CCORR_NORMED,
            "sqdiff": cv2.TM_SQDIFF,
            "sqdiff_normed": cv2.TM_SQDIFF_NORMED,
        }
        # 记录当前使用的方法名称（也用于后续选择具体 OpenCV method）
        self.method_name = method
        # 匹配阈值（越高越严格；sqdiff 类方法会在内部换算）
        self.threshold = threshold
    
    def load_image(self, source: Union[str, np.ndarray, bytes, bytearray, memoryview]) -> Optional[np.ndarray]:
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
    
    def match_template(self, source: np.ndarray, template: np.ndarray) -> Tuple[float, Tuple[int, int]]:
        # 1) 根据 method_name 选择实际使用的 OpenCV 匹配方法
        if self.method_name == "auto":
            method = cv2.TM_CCOEFF_NORMED
        else:
            method = self.methods.get(self.method_name, cv2.TM_CCOEFF_NORMED)
        
        # 2) 计算模板匹配得分图（result 是二维矩阵，每个像素代表一个候选位置的得分）
        result = cv2.matchTemplate(source, template, method)
        
        # 3) 在得分图中取最小/最大值及其位置（不同方法对应不同“越好”方向）
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # 4) 统一输出为“confidence 越大越好”的语义，并确定最佳匹配左上角坐标
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1 - min_val
            top_left = min_loc
        else:
            confidence = max_val
            top_left = max_loc
        
        # 5) 返回最佳匹配的置信度与左上角坐标
        return confidence, top_left
    
    def match_all_templates(self, source: np.ndarray, template: np.ndarray) -> List[Tuple[Tuple[int, int], float]]:
        # 1) 根据 method_name 选择实际使用的 OpenCV 匹配方法
        if self.method_name == "auto":
            method = cv2.TM_CCOEFF_NORMED
        else:
            method = self.methods.get(self.method_name, cv2.TM_CCOEFF_NORMED)
        
        # 2) 计算模板匹配得分图（二维矩阵）
        result = cv2.matchTemplate(source, template, method)
        
        locations = []
        # 3) 按方法类型确定“满足阈值的候选点”：
        #    - sqdiff 类：数值越小越好，因此找 <= (1-threshold)
        #    - 其他类：数值越大越好，因此找 >= threshold
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            threshold_val = 1 - self.threshold
            locs = np.where(result <= threshold_val)
        else:
            threshold_val = self.threshold
            locs = np.where(result >= threshold_val)
        
        # 4) 把所有候选点转成 (左上角坐标, 置信度) 列表
        for pt in zip(*locs[::-1]):
            if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                confidence = 1 - result[pt[1], pt[0]]
            else:
                confidence = result[pt[1], pt[0]]
            locations.append((pt, confidence))
        
        # 5) 非极大值抑制（NMS）：去掉重叠过大的重复框，只保留更“好”的候选
        locations = self._non_max_suppression(locations, template.shape[1], template.shape[0])
        
        # 6) 返回筛选后的匹配结果
        return locations
    
    def _non_max_suppression(self, locations: List[Tuple[Tuple[int, int], float]], 
                              w: int, h: int, overlap_thresh: float = 0.3) -> List[Tuple[Tuple[int, int], float]]:
        # 1) 无候选直接返回
        if len(locations) == 0:
            return []
        
        # 2) 按置信度从高到低排序，优先保留最可信的匹配
        locations = sorted(locations, key=lambda x: x[1], reverse=True)
        
        pick = []
        
        # 3) 逐个取出“当前最优”的候选，并剔除与其重叠过大的其它候选
        while len(locations) > 0:
            current = locations[0]
            pick.append(current)
            locations = locations[1:]
            
            remaining = []
            for loc in locations:
                pt, conf = loc
                
                # 计算两个候选框的交集区域（都假设同模板尺寸 w*h）
                xx1 = max(current[0][0], pt[0])
                yy1 = max(current[0][1], pt[1])
                xx2 = min(current[0][0] + w, pt[0] + w)
                yy2 = min(current[0][1] + h, pt[1] + h)
                
                w_intersect = max(0, xx2 - xx1)
                h_intersect = max(0, yy2 - yy1)
                
                # 用“交集面积 / 模板面积”粗略衡量重叠程度（0~1）
                overlap = (w_intersect * h_intersect) / (w * h)
                
                # 重叠不超过阈值的保留为候选；重叠过大的丢弃（避免重复标框）
                if overlap <= overlap_thresh:
                    remaining.append(loc)
            
            locations = remaining
        
        # 4) 返回保留下来的候选
        return pick
    
    def draw_matches(self, source: np.ndarray, template: np.ndarray, 
                     locations: List[Tuple[Tuple[int, int], float]]) -> np.ndarray:
        # 1) 复制一份源图用于绘制（不污染原图）
        result = source.copy()
        # 2) 获取模板宽高，用于把“左上角点”还原成矩形框
        h, w = template.shape[:2]
        
        # 3) 遍历所有匹配项，在图上画框并写上置信度
        for i, (top_left, confidence) in enumerate(locations):
            bottom_right = (top_left[0] + w, top_left[1] + h)
            
            # 画矩形框
            cv2.rectangle(result, top_left, bottom_right, (0, 255, 0), 2)
            
            # 生成文字标签
            label = f"Match {i+1}: {confidence:.2f}"
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            # 计算标签背景的位置，尽量显示在框上方
            label_top = max(top_left[1] - label_size[1] - 5, 0)
            label_bottom = label_top + label_size[1] + baseline
            
            # 画标签背景（绿色底）
            cv2.rectangle(result, 
                         (top_left[0], label_top),
                         (top_left[0] + label_size[0], label_bottom),
                         (0, 255, 0), -1)
            
            # 写标签文字（黑字）
            cv2.putText(result, label, 
                       (top_left[0], label_top + label_size[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        # 4) 返回已标注的结果图
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
    # 1) 创建匹配器（这里强制使用 ccoeff_normed 方法）
    matcher = TemplateMatcher(method='ccoeff_normed', threshold=threshold)
    
    # 2) 加载源图
    source = matcher.load_image(source_path)
    if source is None:
        return False, None, []
    
    # 3) 加载模板图
    template = matcher.load_image(template_path)
    if template is None:
        return False, None, []
    
    # 4) 模板尺寸校验
    if template.shape[0] > source.shape[0] or template.shape[1] > source.shape[1]:
        print("错误: 模板图片尺寸大于源图片")
        return False, None, []
    
    # 5) 执行匹配（全部匹配或最佳匹配）
    if find_all:
        locations = matcher.match_all_templates(source, template)
    else:
        confidence, top_left = matcher.match_template(source, template)
        if confidence >= threshold:
            locations = [(top_left, confidence)]
        else:
            locations = []
    
    # 6) 无匹配直接返回失败
    if len(locations) == 0:
        return False, None, []
    
    # 7) 在源图上绘制匹配框
    result_image = matcher.draw_matches(source, template, locations)
    
    if output_path is not None:
        out_path = output_path
        if os.path.isdir(output_path):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(output_path, f"matched_{ts}.png")
        cv2.imwrite(out_path, result_image)

    if show_result:
        cv2.imshow("Matched Result", result_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    sys_util.save_debug_image(result_image, "detected")
    # 10) 返回结果：是否成功、结果图、匹配列表
    return True, result_image, locations


def main():
    # 这里是脚本直接运行时的示例入口
    source_path = "debug_shots\mhxy_client_20260419_011140.png"

    # 调用对外接口执行匹配
    success, _, locations = match_template(
        source_path,
        template_path="assets\dituguangquan_0.6.PNG",
        threshold=0.6,
        find_all=True,
    )
    # 打印匹配坐标信息（便于后续程序使用）
    print("匹配位置信息:", locations)
    if not success:
        print("\n匹配失败")


if __name__ == "__main__":
    # 直接运行该文件时执行 main()
    main()
