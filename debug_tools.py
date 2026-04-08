import cv2
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mhxy_escort_bot.main import MHXYEscortBot

def capture_ui_samples():
    """采集游戏界面样本用于调试"""
    print("开始采集游戏界面样本...")
    
    bot = MHXYEscortBot()
    if not bot.find_game_window():
        print("未找到游戏窗口！")
        return
        
    bot.activate_window()
    time.sleep(1)
    
    # 采集当前界面截图
    screenshot = bot.capture_screen()
    if screenshot is not None:
        cv2.imwrite('debug_current_view.png', screenshot)
        print("已保存当前界面截图: debug_current_view.png")
        
        # 显示截图尺寸
        height, width = screenshot.shape[:2]
        print(f"截图尺寸: {width}x{height}")
        
        # 显示HSV转换后的图像信息
        hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
        print("HSV色彩空间转换完成")
    else:
        print("截图失败")

def test_npc_detection():
    """测试NPC检测功能"""
    print("测试NPC检测功能...")
    
    bot = MHXYEscortBot()
    if not bot.find_game_window():
        print("未找到游戏窗口！")
        return
        
    bot.activate_window()
    time.sleep(1)
    
    # 导入并测试TreasureHuntSystem
    from mhxy_escort_bot.treasure_hunt import TreasureHuntSystem
    treasure_sys = TreasureHuntSystem(bot)
    
    npc_pos = treasure_sys.locate_tavern_npc()
    if npc_pos:
        print(f"检测到NPC位置: {npc_pos}")
    else:
        print("未检测到NPC")

if __name__ == "__main__":
    print("调试工具菜单:")
    print("1. 采集界面样本")
    print("2. 测试NPC检测")
    
    choice = input("请选择功能 (1/2): ")
    
    if choice == "1":
        capture_ui_samples()
    elif choice == "2":
        test_npc_detection()
    else:
        print("无效选择")