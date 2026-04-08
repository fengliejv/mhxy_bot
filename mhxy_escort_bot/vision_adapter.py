import base64
import requests
import json
import cv2
import numpy as np
from typing import Optional, Tuple
import logging

class VisionModelAdapter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        self.logger = logging.getLogger(__name__)

    def analyze_image(self, image_array, prompt: str) -> Optional[str]:
        """
        使用视觉大模型分析图像
        """
        try:
            # 将numpy数组编码为base64
            _, buffer = cv2.imencode('.jpg', image_array)
            base64_image = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "model": "qwen-vl-plus",  # 选择适合的视觉模型
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "image": f"data:image/jpeg;base64,{base64_image}",
                                },
                                {
                                    "text": prompt
                                }
                            ]
                        }
                    ]
                },
                "parameters": {
                    "temperature": 0.1
                }
            }
            
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(self.base_url, headers=headers, data=json.dumps(payload))
            
            if response.status_code == 200:
                result = response.json()
                if 'output' in result and 'choices' in result['output']:
                    return result['output']['choices'][0]['message']['content'][0]['text']
            elif response.status_code == 401:
                self.logger.error(f"API密钥验证失败: {response.status_code}, {response.text}")
                return None
            else:
                self.logger.error(f"视觉模型请求失败: {response.status_code}, {response.text}")
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"网络请求错误: {str(e)}")
        except Exception as e:
            self.logger.error(f"视觉模型分析出错: {str(e)}")
            
        return None

    def detect_combat_status_vision(self, screen_image) -> bool:
        """
        使用视觉大模型检测是否处于战斗状态
        """
        prompt = "请分析这张梦幻西游游戏截图，判断角色是否处于战斗状态。如果是战斗状态，请返回'战斗中'，如果不是请返回'非战斗'。只需要回答这两个词之一。"
        result = self.analyze_image(screen_image, prompt)
        
        if result and '战斗中' in result:
            return True
        return False

    def detect_npc_location(self, screen_image) -> Optional[Tuple[int, int]]:
        """
        使用视觉大模型定位NPC位置
        """
        prompt = "请分析这张梦幻西游游戏截图，找出酒馆店小二或其他NPC的位置坐标。请返回坐标格式为(x,y)，例如'坐标(450,320)'。"
        result = self.analyze_image(screen_image, prompt)
        
        # 解析返回的坐标
        import re
        coord_match = re.search(r'坐标\((\d+),(\d+)\)', result or "")
        if coord_match:
            x, y = int(coord_match.group(1)), int(coord_match.group(2))
            return (x, y)
        return None

    def detect_treasure_map_elements(self, screen_image) -> dict:
        """
        检测藏宝图相关元素
        """
        prompt = "请分析这张梦幻西游游戏截图，识别以下游戏元素：1. 是否显示藏宝图界面；2. 是否有挖掘按钮；3. 是否有战斗提示；4. 角色血量状态。请分别说明这四个方面的内容。"
        result = self.analyze_image(screen_image, prompt)
        
        elements = {
            'has_treasure_map_interface': '藏宝图' in result if result else False,
            'has_dig_button': '挖掘' in result or '按钮' in result if result else False,
            'has_combat_prompt': '战斗' in result if result else False,
            'hp_status': '血量' in result if result else 'unknown'
        }
        
        return elements