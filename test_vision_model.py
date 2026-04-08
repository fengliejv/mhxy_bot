import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_vision_model():
    """测试视觉大模型连接"""
    print("正在测试视觉大模型连接...")
    
    try:
        from mhxy_escort_bot.vision_adapter import VisionModelAdapter
        
        # 使用提供的API密钥
        api_key = "sk-iyfyuubfvknniobmxbjylczlflucqcicqzzhrolmjqofwxog"
        vision_adapter = VisionModelAdapter(api_key)
        
        # 测试基本连接
        print("视觉大模型适配器创建成功")
        
        # 尝试捕获游戏画面并进行分析
        from mhxy_escort_bot.main import MHXYEscortBot
        bot = MHXYEscortBot()
        
        if bot.find_game_window():
            print("找到游戏窗口")
            bot.activate_window()
            import time
            time.sleep(1)
            
            screenshot = bot.capture_screen()
            if screenshot is not None:
                print(f"截图成功，尺寸: {screenshot.shape}")
                
                # 测试视觉模型分析
                print("正在测试视觉模型分析功能...")
                result = vision_adapter.detect_combat_status_vision(screenshot)
                print(f"战斗状态检测结果: {result}")
                
                # 测试NPC检测
                npc_result = vision_adapter.detect_npc_location(screenshot)
                print(f"NPC位置检测结果: {npc_result}")
                
                return True
            else:
                print("截图失败")
        else:
            print("未找到游戏窗口")
            
    except Exception as e:
        print(f"测试过程中出现错误: {str(e)}")
        import traceback
        traceback.print_exc()
        
    return False

if __name__ == "__main__":
    test_vision_model()