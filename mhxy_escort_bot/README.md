# 梦幻西游押镖机器人

这是一个自动化梦幻西游押镖任务的Python脚本，能够自动完成从接任务到完成任务的整个流程。

## 功能特性

- 自动寻找酒馆店小二接取押镖任务
- 智能导航至押镖目的地
- 自动战斗系统，击败沿途强盗
- 背包和状态管理，自动补充消耗品
- 使用传送道具快速移动

## 依赖库

- opencv-python
- numpy
- Pillow
- pyautogui
- pywin32 (仅限Windows)

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

1. 确保梦幻西游客户端已启动并登录游戏
2. 运行主脚本：

```bash
python main.py
```

## 配置说明

所有配置项都在 `config.py` 文件中，包括：

- 游戏窗口标题
- 图像识别阈值
- 状态监控阈值
- 物品管理设置
- 快捷键映射

## 注意事项

1. 使用前请确保快捷键设置与配置文件一致
2. 机器人基于图像识别工作，分辨率和游戏设置可能影响准确性
3. 请适度使用，避免违反游戏规则

## 模块说明

- `main.py`: 主控制器，协调各个模块
- `image_recognition.py`: 图像识别和模板匹配
- `npc_interaction.py`: NPC交互逻辑
- `navigation.py`: 地图导航系统
- `combat.py`: 战斗系统
- `inventory.py`: 库存管理
- `config.py`: 配置参数