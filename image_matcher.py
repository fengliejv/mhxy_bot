#!/usr/bin/env python3
"""
图像模板匹配脚本
在图A中检测图B对应的元素并标记出来
"""

import cv2
import numpy as np
import argparse
import os
from typing import List, Tuple, Optional
import datetime
import os

# 默认输出目录
DEFAULT_OUTPUT_DIR = "matched_results"
class TemplateMatcher:
    def __init__(self, method: str = "auto", threshold: float = 0.8):
        self.methods = {
            "auto": None,
            "ccoeff": cv2.TM_CCOEFF,
            "ccoeff_normed": cv2.TM_CCOEFF_NORMED,
            "ccorr": cv2.TM_CCORR,
            "ccorr_normed": cv2.TM_CCORR_NORMED,
            "sqdiff": cv2.TM_SQDIFF,
            "sqdiff_normed": cv2.TM_SQDIFF_NORMED,
        }
        self.method_name = method
        self.threshold = threshold
    
    def load_image(self, path: str) -> Optional[np.ndarray]:
        if not os.path.exists(path):
            print(f"错误: 图片不存在 - {path}")
            return None
        
        img = cv2.imread(path)
        if img is None:
            print(f"错误: 无法读取图片 - {path}")
            return None
        
        return img
    
    def match_template(self, source: np.ndarray, template: np.ndarray) -> Tuple[float, Tuple[int, int]]:
        if self.method_name == "auto":
            method = cv2.TM_CCOEFF_NORMED
        else:
            method = self.methods.get(self.method_name, cv2.TM_CCOEFF_NORMED)
        
        result = cv2.matchTemplate(source, template, method)
        
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            confidence = 1 - min_val
            top_left = min_loc
        else:
            confidence = max_val
            top_left = max_loc
        
        return confidence, top_left
    
    def match_all_templates(self, source: np.ndarray, template: np.ndarray) -> List[Tuple[Tuple[int, int], float]]:
        if self.method_name == "auto":
            method = cv2.TM_CCOEFF_NORMED
        else:
            method = self.methods.get(self.method_name, cv2.TM_CCOEFF_NORMED)
        
        result = cv2.matchTemplate(source, template, method)
        
        locations = []
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            threshold_val = 1 - self.threshold
            locs = np.where(result <= threshold_val)
        else:
            threshold_val = self.threshold
            locs = np.where(result >= threshold_val)
        
        for pt in zip(*locs[::-1]):
            if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                confidence = 1 - result[pt[1], pt[0]]
            else:
                confidence = result[pt[1], pt[0]]
            locations.append((pt, confidence))
        
        locations = self._non_max_suppression(locations, template.shape[1], template.shape[0])
        
        return locations
    
    def _non_max_suppression(self, locations: List[Tuple[Tuple[int, int], float]], 
                              w: int, h: int, overlap_thresh: float = 0.3) -> List[Tuple[Tuple[int, int], float]]:
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
    
    def draw_matches(self, source: np.ndarray, template: np.ndarray, 
                     locations: List[Tuple[Tuple[int, int], float]]) -> np.ndarray:
        result = source.copy()
        h, w = template.shape[:2]
        
        for i, (top_left, confidence) in enumerate(locations):
            bottom_right = (top_left[0] + w, top_left[1] + h)
            
            cv2.rectangle(result, top_left, bottom_right, (0, 255, 0), 2)
            
            label = f"Match {i+1}: {confidence:.2f}"
            label_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            
            label_top = max(top_left[1] - label_size[1] - 5, 0)
            label_bottom = label_top + label_size[1] + baseline
            
            cv2.rectangle(result, 
                         (top_left[0], label_top),
                         (top_left[0] + label_size[0], label_bottom),
                         (0, 255, 0), -1)
            
            cv2.putText(result, label, 
                       (top_left[0], label_top + label_size[1]),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        
        return result
    
    def find_and_mark(self, source_path: str, template_path: str, 
                      output_path: str = None, find_all: bool = True) -> bool:
        print(f"加载源图片: {source_path}")
        source = self.load_image(source_path)
        if source is None:
            return False
        
        print(f"加载模板图片: {template_path}")
        template = self.load_image(template_path)
        if template is None:
            return False
        
        if template.shape[0] > source.shape[0] or template.shape[1] > source.shape[1]:
            print("错误: 模板图片尺寸大于源图片")
            return False
        
        print(f"源图片尺寸: {source.shape[1]} x {source.shape[0]}")
        print(f"模板图片尺寸: {template.shape[1]} x {template.shape[0]}")
        print(f"匹配阈值: {self.threshold}")
        
        if find_all:
            print("\n正在检测所有匹配项...")
            locations = self.match_all_templates(source, template)
        else:
            print("\n正在检测最佳匹配项...")
            confidence, top_left = self.match_template(source, template)
            if confidence >= self.threshold:
                locations = [(top_left, confidence)]
            else:
                locations = []
        
        if len(locations) == 0:
            print(f"\n未找到匹配项 (阈值: {self.threshold})")
            return False
        
        print(f"\n找到 {len(locations)} 个匹配项:")
        for i, (pos, conf) in enumerate(locations, 1):
            print(f"  匹配 {i}: 位置 ({pos[0]}, {pos[1]}), 置信度 {conf:.4f}")
        
        result_image = self.draw_matches(source, template, locations)
        
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(source_path))[0]
            output_path = f"{base_name}_matched.jpg"
        
        cv2.imwrite(output_path, result_image)
        print(f"\n结果已保存到: {output_path}")
        
        cv2.imshow("Matched Result", result_image)
        print("\n按任意键关闭预览窗口...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        
        return True



def generate_output_path(source_path: str) -> str:
    """
    根据当前时间戳生成输出文件路径，保存在默认目录下
    """
    # 确保输出目录存在
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    
    # 获取源文件名（不含扩展名）
    base_name = os.path.splitext(os.path.basename(source_path))[0]
    
    # 生成时间戳字符串
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 组合输出路径
    output_filename = f"{base_name}_{timestamp}.jpg"
    return os.path.join(DEFAULT_OUTPUT_DIR, output_filename)


#对外暴露的函数接口，供其他模块调用
def match_template(source_path: str,
                   template_path: str,
                   output_path: str = DEFAULT_OUTPUT_DIR,
                   threshold: float = 0.8,
                   find_all: bool = True,
                   show_result: bool = False) -> Tuple[bool, Optional[np.ndarray], List[Tuple[Tuple[int, int], float]]]:
    """
    图像模板匹配函数接口
    
    参数:
        source_path: 源图片路径
        template_path: 模板图片路径
        output_path: 输出图片路径，为 None 时不保存
        threshold: 匹配阈值 (0-1)
        find_all: 是否查找所有匹配项
        show_result: 是否显示结果窗口
    
    返回:
        success: 是否成功匹配
        result_image: 标记后的结果图像，失败时为 None
        locations: 匹配位置列表，每个元素为 ((x, y), confidence)
    """
    matcher = TemplateMatcher(method='ccoeff_normed', threshold=threshold)
    
    source = matcher.load_image(source_path)
    if source is None:
        return False, None, []
    
    template = matcher.load_image(template_path)
    if template is None:
        return False, None, []
    
    if template.shape[0] > source.shape[0] or template.shape[1] > source.shape[1]:
        print("错误: 模板图片尺寸大于源图片")
        return False, None, []
    
    if find_all:
        locations = matcher.match_all_templates(source, template)
    else:
        confidence, top_left = matcher.match_template(source, template)
        if confidence >= threshold:
            locations = [(top_left, confidence)]
        else:
            locations = []
    
    if len(locations) == 0:
        return False, None, []
    
    result_image = matcher.draw_matches(source, template, locations)
    
    if output_path is not None:
        cv2.imwrite(output_path, result_image)
    
    if show_result:
        cv2.imshow("Matched Result", result_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    return True, result_image, locations


def main():
    dir = "debug_shots/match"
    source_path = "debug_shots\mhxy_client_20260419_011140.png"

    success, _, locations = match_template(
        source_path,
        template_path="assets\dituguangquan_0.6.PNG",
        output_path=f"{dir}/matched.jpg",
        threshold=0.6,
        find_all=True,
        show_result=True
    )
    print("匹配位置信息:", locations)
    if not success:
        print("\n匹配失败")


if __name__ == "__main__":
    main()
