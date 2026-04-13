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


def main():
    parser = argparse.ArgumentParser(
        description="图像模板匹配工具 - 在图A中检测并标记图B的元素",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python image_matcher.py source.jpg template.jpg
  python image_matcher.py source.jpg template.jpg -o result.jpg
  python image_matcher.py source.jpg template.jpg -t 0.7
  python image_matcher.py source.jpg template.jpg --single
        """
    )
    
    parser.add_argument("source", help="源图片路径 (图A)")
    parser.add_argument("template", help="模板图片路径 (图B)")
    parser.add_argument("-o", "--output", help="输出图片路径 (默认: source_matched.jpg)")
    parser.add_argument("-t", "--threshold", type=float, default=0.8,
                       help="匹配阈值 (0-1, 默认: 0.8)")
    # parser.add_argument("-m", "--method", 
    #                    choices=["auto", "ccoeff", "ccoeff_normed", "ccorr", 
    #                            "ccorr_normed", "sqdiff", "sqdiff_normed"],
    #                    default="auto",
    #                    help="匹配方法 (默认: auto)")
    parser.add_argument("--single", action="store_true",
                       help="只查找最佳匹配项 (默认: 查找所有)")
    
    args = parser.parse_args()
    
    if args.threshold < 0 or args.threshold > 1:
        print("错误: 阈值必须在 0 到 1 之间")
        return
    
    matcher = TemplateMatcher(method='ccoeff_normed', threshold=args.threshold)
    
    success = matcher.find_and_mark(
        source_path=args.source,
        template_path=args.template,
        output_path=args.output,
        find_all=not args.single
    )
    
    if not success:
        print("\n匹配失败")


if __name__ == "__main__":
    main()
