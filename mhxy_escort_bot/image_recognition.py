"""
图像识别和模板匹配工具
用于识别游戏中的NPC、UI元素等
"""

import cv2
import numpy as np
from typing import Tuple, Optional, List
import os


class ImageRecognition:
    def __init__(self):
        self.templates = {}
    
    def load_template(self, name: str, template_path: str):
        """
        加载模板图片
        """
        if os.path.exists(template_path):
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            self.templates[name] = template
            return True
        else:
            print(f"模板文件不存在: {template_path}")
            return False
    
    def find_template_on_screen(self, screen: np.ndarray, template: np.ndarray, threshold: float = 0.8) -> Optional[Tuple[int, int, float]]:
        """
        在屏幕截图中查找模板
        返回: (x, y, confidence) 或 None
        """
        if screen is None or template is None:
            return None
        
        # 执行模板匹配
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        
        # 找到最大匹配值的位置
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        if max_val >= threshold:
            # 返回匹配位置和置信度
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)
        
        return None
    
    def find_multiple_templates(self, screen: np.ndarray, template: np.ndarray, threshold: float = 0.8, 
                               min_distance: int = 50) -> List[Tuple[int, int, float]]:
        """
        在屏幕截图中查找多个相似模板
        使用非极大值抑制去除距离过近的重复检测
        """
        if screen is None or template is None:
            return []
        
        # 执行模板匹配
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        
        # 找到所有满足阈值的匹配点
        locations = np.where(result >= threshold)
        scores = result[locations]
        
        # 组装坐标和分数
        detections = []
        for i in range(len(locations[0])):
            y, x = locations[0][i], locations[1][i]
            h, w = template.shape[:2]
            center_x = x + w // 2
            center_y = y + h // 2
            score = scores[i]
            detections.append((center_x, center_y, score))
        
        # 应用非极大值抑制
        filtered_detections = self.non_max_suppression(detections, min_distance)
        
        return filtered_detections
    
    def non_max_suppression(self, detections: List[Tuple[int, int, float]], min_distance: int) -> List[Tuple[int, int, float]]:
        """
        非极大值抑制，去除距离过近的重复检测
        """
        if len(detections) == 0:
            return []
        
        # 按置信度排序
        detections = sorted(detections, key=lambda x: x[2], reverse=True)
        
        keep = []
        while detections:
            # 保留置信度最高的检测
            current = detections.pop(0)
            keep.append(current)
            
            # 移除与当前检测距离过近的其他检测
            detections = [
                d for d in detections 
                if self.distance(current[:2], d[:2]) > min_distance
            ]
        
        return keep
    
    def distance(self, point1: Tuple[int, int], point2: Tuple[int, int]) -> float:
        """
        计算两点间距离
        """
        return np.sqrt((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2)
    
    def detect_color_region(self, screen: np.ndarray, lower_color: Tuple[int, int, int], 
                           upper_color: Tuple[int, int, int], min_area: int = 100) -> Optional[Tuple[int, int]]:
        """
        检测特定颜色区域
        """
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, lower_color, upper_color)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 找到最大的符合条件的轮廓
        largest_contour = None
        max_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > max_area and area > min_area:
                max_area = area
                largest_contour = contour
        
        if largest_contour is not None:
            # 计算轮廓中心
            M = cv2.moments(largest_contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                return (cx, cy)
        
        return None


# 预设的颜色范围
COLOR_PRESETS = {
    # 酒馆店小二可能的颜色（需要根据实际游戏中NPC的颜色调整）
    'tavern_npc_red': ((0, 50, 50), (10, 255, 255)),  # 红色系
    'tavern_npc_blue': ((100, 50, 50), (130, 255, 255)),  # 蓝色系
    'tavern_npc_yellow': ((20, 50, 50), (30, 255, 255)),  # 黄色系
    # 战斗界面红色血条
    'health_bar_red': ((0, 100, 100), (10, 255, 255)),
    # 特定UI元素颜色
    'ui_gold': ((20, 100, 100), (40, 255, 255)),  # 金色UI
}