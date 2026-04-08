"""
地图导航模块
处理在梦幻西游中的移动和导航
"""

import time
import cv2
import numpy as np
import pyautogui
from typing import Tuple, Optional, List
from .main import MHXYEscortBot


class NavigationSystem:
    def __init__(self, bot: MHXYEscortBot):
        self.bot = bot
        self.current_map = None
        self.destination_map = None
        self.path = []
        
        # 预设的地图传送点坐标
        self.transport_points = {
            # 主要城市之间的传送点（需要根据实际游戏调整）
            '长安城': {'x': 375, 'y': 523},
            '建邺城': {'x': 592, 'y': 473},
            '朱紫国': {'x': 649, 'y': 373},
            '长寿村': {'x': 205, 'y': 115},
            '傲来国': {'x': 500, 'y': 100},
            '大唐国境': {'x': 400, 'y': 300},
            # 更多地图坐标...
        }
        
        # 传送符和导标旗的快捷键（需要根据玩家设置调整）
        self.teleport_items = {
            '传送符': 'F1',  # 示例快捷键
            '导标旗': 'F2'   # 示例快捷键
        }
    
    def detect_current_map(self) -> Optional[str]:
        """
        检测当前所在地图
        """
        screen = self.bot.capture_screen()
        if screen is None:
            return None
        
        # 这里需要实现地图识别逻辑
        # 可以通过检测地图边框、特定建筑、地图名称等方式
        # 暂时返回模拟结果
        return "长安城"  # 示例
    
    def set_destination(self, destination: str):
        """
        设置目标地图
        """
        self.destination_map = destination
        self.bot.logger.info(f"设置目标地图: {destination}")
    
    def calculate_path(self, start_map: str, end_map: str) -> List[str]:
        """
        计算从起点到终点的路径
        """
        # 简化的路径计算，实际游戏中可能需要更复杂的寻路算法
        # 这里使用预设的路径规则
        path_map = {
            ('长安城', '建邺城'): ['大唐国境'],
            ('建邺城', '长安城'): ['大唐国境'],
            ('长安城', '长寿村'): ['大唐国境'],
            ('长寿村', '长安城'): ['大唐国境'],
            # 添加更多路径规则...
        }
        
        if (start_map, end_map) in path_map:
            path = [start_map] + path_map[(start_map, end_map)] + [end_map]
        elif (end_map, start_map) in path_map:
            path = [start_map] + path_map[(end_map, start_map)][::-1] + [end_map]
        else:
            # 默认路径，经过长安城中转
            path = [start_map, '长安城', end_map]
        
        return path
    
    def navigate_to_destination(self) -> bool:
        """
        导航到目的地
        """
        if not self.destination_map:
            self.bot.logger.error("未设置目标地图")
            return False
        
        current_map = self.detect_current_map()
        if not current_map:
            self.bot.logger.error("无法检测当前地图")
            return False
        
        self.bot.logger.info(f"当前地图: {current_map}, 目标地图: {self.destination_map}")
        
        if current_map == self.destination_map:
            self.bot.logger.info("已在目标地图")
            return True
        
        # 计算路径
        path = self.calculate_path(current_map, self.destination_map)
        self.bot.logger.info(f"导航路径: {' -> '.join(path)}")
        
        # 按路径逐步导航
        for i in range(len(path) - 1):
            from_map = path[i]
            to_map = path[i + 1]
            
            success = self.travel_between_maps(from_map, to_map)
            if not success:
                self.bot.logger.error(f"无法从 {from_map} 前往 {to_map}")
                return False
            
            # 等待地图切换完成
            time.sleep(3.0)
        
        self.bot.logger.info("成功到达目标地图")
        return True
    
    def travel_between_maps(self, from_map: str, to_map: str) -> bool:
        """
        在两个地图之间移动
        """
        self.bot.logger.info(f"正在前往: {to_map}")
        
        # 检查是否有直接的传送方式
        if self.use_teleport_item(to_map):
            return True
        
        # 否则使用步行或其他方式
        return self.walk_to_adjacent_map(from_map, to_map)
    
    def use_teleport_item(self, target_map: str) -> bool:
        """
        使用传送道具前往目标地图
        """
        if target_map in self.transport_points:
            # 使用传送符或导标旗
            teleport_used = False
            
            # 尝试使用传送符
            if self.has_teleport_item('传送符'):
                self.use_item_shortcut('传送符')
                time.sleep(2.0)  # 等待传送动画
                
                # 选择目标地图
                self.select_target_map(target_map)
                teleport_used = True
            
            # 如果传送符不可用，尝试导标旗
            elif self.has_teleport_item('导标旗') and target_map in self.transport_points:
                self.use_item_shortcut('导标旗')
                time.sleep(1.0)
                
                # 点击目标位置
                coords = self.transport_points[target_map]
                self.bot.click_position(coords['x'], coords['y'])
                teleport_used = True
        
        return False  # 简化实现
    
    def has_teleport_item(self, item_name: str) -> bool:
        """
        检查是否拥有传送道具
        """
        # 这里需要实现物品检测逻辑
        # 可以通过检测背包界面或快捷栏中的图标
        return True  # 简化实现
    
    def use_item_shortcut(self, item_name: str):
        """
        使用物品快捷键
        """
        if item_name in self.teleport_items:
            key = self.teleport_items[item_name]
            pyautogui.press(key)
            self.bot.logger.info(f"使用传送道具: {item_name} (快捷键: {key})")
    
    def select_target_map(self, target_map: str):
        """
        选择目标地图
        """
        # 在传送界面中选择目标地图
        # 这需要根据实际游戏界面调整坐标
        screen_width = self.bot.screenshot_region[2] - self.bot.screenshot_region[0]
        screen_height = self.bot.screenshot_region[3] - self.bot.screenshot_region[1]
        
        # 示例：点击传送界面中的目标地图选项
        # 实际坐标需要在游戏中确定
        self.bot.click_position(int(screen_width * 0.5), int(screen_height * 0.6))
    
    def walk_to_adjacent_map(self, from_map: str, to_map: str) -> bool:
        """
        步行前往相邻地图
        """
        self.bot.logger.info(f"步行从 {from_map} 前往 {to_map}")
        
        # 获取两个地图之间的连接点坐标
        # 这需要预先配置好各地图的边界连接点
        connection_points = self.get_connection_points(from_map, to_map)
        
        if not connection_points:
            self.bot.logger.error(f"未找到 {from_map} 和 {to_map} 之间的连接点")
            return False
        
        # 移动到连接点
        for point in connection_points:
            self.move_to_coordinate(point['x'], point['y'])
            
            # 检查是否已经切换到目标地图
            time.sleep(1.0)
            current_map = self.detect_current_map()
            if current_map == to_map:
                return True
        
        return False
    
    def get_connection_points(self, from_map: str, to_map: str) -> List[dict]:
        """
        获取两个地图之间的连接点
        """
        # 预设的连接点数据（需要根据实际游戏地图配置）
        connections = {
            ('长安城', '大唐国境'): [{'x': 375, 'y': 550}],
            ('大唐国境', '长安城'): [{'x': 375, 'y': 490}],
            ('建邺城', '大唐国境'): [{'x': 592, 'y': 500}],
            ('大唐国境', '建邺城'): [{'x': 592, 'y': 450}],
            # 添加更多连接点...
        }
        
        forward = (from_map, to_map)
        backward = (to_map, from_map)
        
        if forward in connections:
            return connections[forward]
        elif backward in connections:
            return connections[backward]
        else:
            return []  # 返回空列表表示没有预设连接点
    
    def move_to_coordinate(self, x: int, y: int):
        """
        移动到指定坐标
        """
        self.bot.logger.info(f"移动到坐标: ({x}, {y})")
        
        # 在梦幻西游中，通常是右键点击地面移动
        # 计算绝对坐标
        abs_x = self.bot.screenshot_region[0] + x
        abs_y = self.bot.screenshot_region[1] + y
        
        # 右键点击移动
        pyautogui.rightClick(abs_x, abs_y)
        
        # 等待移动完成（这里简化处理，实际可能需要检测角色是否还在移动）
        estimated_travel_time = 2.0  # 预估移动时间
        time.sleep(estimated_travel_time)
    
    def avoid_monsters(self):
        """
        避开路上的怪物
        """
        # 检测屏幕上的怪物并避开
        screen = self.bot.capture_screen()
        if screen is None:
            return
        
        # 这里需要实现怪物检测逻辑
        # 可以通过颜色、形状或模板匹配来检测怪物
        monster_positions = self.detect_monsters(screen)
        
        for pos in monster_positions:
            # 实现避怪逻辑
            self.evasive_action(pos)
    
    def detect_monsters(self, screen: np.ndarray) -> List[Tuple[int, int]]:
        """
        检测屏幕上的怪物
        """
        # 简化的怪物检测
        # 实际需要根据游戏中怪物的外观特征进行检测
        monster_positions = []
        
        # 示例：检测特定颜色的怪物
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        
        # 定义怪物可能的颜色范围（需要根据实际游戏调整）
        monster_colors = [
            ((0, 50, 50), (20, 255, 255)),    # 红色怪物
            ((100, 50, 50), (130, 255, 255)), # 蓝色怪物
            ((40, 50, 50), (80, 255, 255)),   # 绿色怪物
        ]
        
        for lower, upper in monster_colors:
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > 500:  # 过滤小面积噪声
                    M = cv2.moments(contour)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        monster_positions.append((cx, cy))
        
        return monster_positions
    
    def evasive_action(self, monster_pos: Tuple[int, int]):
        """
        执行避怪动作
        """
        # 计算远离怪物的方向
        player_center_x = (self.bot.screenshot_region[2] - self.bot.screenshot_region[0]) // 2
        player_center_y = (self.bot.screenshot_region[3] - self.bot.screenshot_region[1]) // 2
        
        monster_x, monster_y = monster_pos
        
        # 计算反方向
        dx = player_center_x - monster_x
        dy = player_center_y - monster_y
        
        # 标准化并放大距离
        length = max(0.1, (dx**2 + dy**2)**0.5)
        move_x = player_center_x + (dx / length) * 100  # 移动100像素的距离
        move_y = player_center_y + (dy / length) * 100
        
        # 移动到安全位置
        self.move_to_coordinate(int(move_x), int(move_y))