"""
测试脚本，用于验证梦幻西游押镖机器人的基本功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mhxy_escort_bot.main import MHXYEscortBot


def test_basic_functionality():
    """测试基本功能"""
    print("开始测试梦幻西游押镖机器人基本功能...")
    
    # 创建机器人实例
    bot = MHXYEscortBot()
    
    # 测试窗口查找功能
    print("\n1. 测试窗口查找功能...")
    found = bot.find_game_window()
    if found:
        print("✓ 成功找到游戏窗口")
    else:
        print("✗ 未找到游戏窗口，请确保梦幻西游已启动")
        return False
    
    # 测试截图功能
    print("\n2. 测试截图功能...")
    screenshot = bot.capture_screen()
    if screenshot is not None:
        height, width = screenshot.shape[:2]
        print(f"✓ 成功截图，尺寸: {width}x{height}")
    else:
        print("✗ 截图失败")
        return False
    
    # 测试状态检测
    print("\n3. 测试状态检测功能...")
    state = bot.detect_game_state()
    print(f"✓ 当前检测到的状态: {state}")
    
    print("\n基本功能测试完成！")
    return True


def main():
    print("="*50)
    print("梦幻西游押镖机器人 - 功能测试")
    print("="*50)
    
    success = test_basic_functionality()
    
    if success:
        print("\n" + "="*50)
        print("所有基本功能测试通过！")
        print("您可以启动完整的押镖流程：python -c \"from mhxy_escort_bot.main import main; main()\"")
        print("="*50)
    else:
        print("\n" + "="*50)
        print("功能测试失败，请检查配置和环境")
        print("="*50)


if __name__ == "__main__":
    main()