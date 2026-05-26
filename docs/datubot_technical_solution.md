# 梦幻西游互通版打图任务技术方案

## 1. 文档目标

本文档基于当前仓库实现，对梦幻西游互通版自动打图能力进行技术梳理，覆盖入口流程、模块分层、配置项、识别策略、运行依赖、异常点和后续演进方向。本文档描述的是“当前已实现方案”，不是完全理想化目标设计。

## 2. 目标与边界

### 2.1 目标

实现一次完整的自动打图流程，核心链路包括：

1. 清理游戏界面，进入稳定操作态
2. 前往长安酒店并领取宝图任务
3. 从任务界面提取强盗名称、地图名称和坐标
4. 按地图名称执行对应跑图策略
5. 在目标地图中识别并点击目标强盗
6. 进入战斗后执行基础自动攻击

### 2.2 当前边界

当前实现聚焦“单次打图执行”，入口脚本只执行一次完整流程，不包含：

- 多轮任务循环调度
- 背包管理和补给策略
- 宝图任务结果汇总与持久化
- 完整状态机与断点恢复
- 所有地图的全量兼容

## 3. 入口与总体架构

### 3.1 入口脚本

入口文件为 `run_datubot.py`：

```python
from bmad.datubot import excute_datu_once

if __name__ == "__main__":
    excute_datu_once()
```

入口职责非常单一，仅调用一次 `excute_datu_once()`，因此主流程编排集中在 `bmad/datubot.py`。

### 3.2 总体分层

当前实现可以拆为 6 层：

1. 任务编排层：`bmad/datubot.py`
2. 路线策略层：`bmad/route_strategies.py`
3. 视觉交互层：`bmad/vision_bot.py`
4. 设备执行层：`bmad/adb_util.py`
5. 图像与 OCR 能力层：`bmad/image_matcher.py`、`bmad/local_ocr_util.py`
6. 配置与环境层：`bmad/botconfig.py`

此外，宝图信息提取依赖大模型服务：

- 业务入口：`bmad/agent_service.py`
- LLM 封装：`bmad/llm/siliconflow.py`
- 兼容导出：`bmad/llm/vision_router.py`

### 3.3 架构关系

```text
run_datubot.py
  -> datubot.py
     -> route_strategies.py
     -> vision_bot.py
        -> adb_util.py
        -> local_ocr_util.py
        -> operator_util.py
           -> image_matcher.py
     -> agent_service.py / llm.vision_router.py
        -> siliconflow.py
     -> botconfig.py
```

## 4. 主流程设计

### 4.1 执行链路

`excute_datu_once()` 的当前顺序如下：

1. `sys_util.clear_debug_capture()`
2. `cleanup_desktop()`
3. `goto_changan_jiudian()`
4. `receive_baotu_task()`
5. `capture_and_extract_baotu_llm()`
6. `route_to_target(llm_map_name, llm_coord)`
7. `attack_target_with_name(llm_qiangdao_name)`
8. `fighting()`

### 4.2 阶段说明

#### 阶段 A：桌面清理

`cleanup_desktop()` 会尝试关闭或收起以下干扰元素：

- 新手引导关闭按钮
- 任务面板关闭按钮
- 对话隐藏按钮
- 自动攻击缩起按钮
- 系统展开按钮
- 隐藏界面按钮
- 隐藏玩家按钮
- 返回按钮
- 地图关闭按钮

该阶段的目的是把界面恢复到“模板匹配和 OCR 更稳定”的状态，降低 UI 遮挡对后续识别的影响。

#### 阶段 B：进入长安酒店并领取任务

`goto_changan_jiudian()` 内部先飞到酒店附近，再执行 `enter_hotel()` 进入酒店。

领取任务由 `receive_baotu_task()` 完成，内部包含最多 3 次重试。单次尝试逻辑为：

1. `close_to_xiaoer()`
2. `go_to_xiaoer()`
3. 点击“领取任务”模板

这里采用的是“混合靠近策略”：

- `close_to_xiaoer()`：使用本地 OCR 识别“店小二”或“挖宝图任务”文本并点击
- `go_to_xiaoer()`：仍然使用店小二 NPC 模板匹配点击

这说明当前实现尚未完全切换为纯 OCR 接近方案，而是 OCR 和模板匹配并存。

#### 阶段 C：识别宝图任务信息

`capture_and_extract_baotu_llm()` 的处理方式为：

1. 点击屏幕中心，尽量激活任务区
2. 点击一次系统返回键清屏
3. 截图
4. 调用 `extract_baotu_info()` 交给大模型抽取结构化信息

结构化输出目标字段为：

- `qiangdao_name`
- `map_name`
- `coord`

该阶段不依赖本地 OCR 做语义解析，而是依赖 SiliconFlow 提供的大模型结构化输出。

#### 阶段 D：自动路由到目标地图

`route_to_target()` 直接调用 `route_strategies.route_by_map()`，由地图名驱动策略分发。

策略层统一要求：

- 必须拿到合法目标坐标
- 地图名必须命中已支持的路由表，未命中则返回 `not_implemented`

#### 阶段 E：识别并攻击目标

`attack_target_with_name(name)` 的当前策略为：

1. 截图
2. 使用本地 OCR 查找黄色文本名称
3. 优先在中心裁剪区域查找，失败后全图查找
4. 命中文本后，以文本中心点上方 95 像素作为点击点
5. 点击对话模板进入战斗

这套逻辑默认目标强盗名称在场景中表现为黄色文字。

#### 阶段 F：战斗处理

`fighting()` 的当前策略较轻量：

1. OCR 识别战斗倒计时区域
2. 如果未检测到数字，认为战斗结束
3. 最多执行 3 轮攻击
4. 每轮调用 `fighting_attack_once()`，完成人物和宠物攻击点击

该实现可以覆盖简单战斗，但不包含复杂战斗策略、目标切换或技能释放决策。

## 5. 模块设计

### 5.1 `datubot.py`

职责：打图业务编排层。

核心特点：

- 聚合全流程步骤
- 负责业务重试与阶段日志
- 定义部分业务专属 OCR 规则
- 不直接承载复杂底层能力实现

其中比较重要的业务函数有：

- `cleanup_desktop()`
- `goto_changan_jiudian()`
- `receive_baotu_task()`
- `close_to_xiaoer()`
- `go_to_xiaoer()`
- `capture_and_extract_baotu_llm()`
- `route_to_target()`
- `attack_target_with_name()`
- `fighting()`

### 5.2 `route_strategies.py`

职责：路线策略分发和跨地图移动。

当前策略分为几类：

- 直接飞行符到主城
- 使用长安导标旗进入入口点
- 复用父路线后执行 NPC/传送
- 到达目标地图后再用地图导航到最终坐标

当前已经支持的地图包括但不限于：

- 狮驼岭
- 魔王寨
- 化生寺
- 东海湾
- 龙宫
- 天宫
- 女儿村
- 大唐国境
- 江南野外
- 普陀山
- 阴曹地府
- 方寸山
- 花果山
- 长寿郊外
- 大唐境外
- 五庄观
- 盘丝洞

此外，还支持部分主城直接飞行：

- 建邺城
- 长寿村
- 朱紫国
- 傲来国
- 宝象国
- 长安城
- 西梁女国

### 5.3 `vision_bot.py`

职责：高层视觉交互封装。

主要能力包括：

- 截图后模板匹配
- 识别多个模板并选最佳命中
- 本地 OCR 文本匹配与点击
- 地图坐标导航
- ROI 裁剪后识别当前坐标
- ROI 裁剪后识别当前地图名

其中有两个重要设计点：

1. 文本匹配支持“按关键词选择图像预处理变体”
2. 地图坐标输入已经适配游戏内数字键盘模板点击，而不是依赖系统输入法

### 5.4 `adb_util.py`

职责：设备层执行。

当前实现特征：

- 统一 ADB 命令入口
- 自动选择设备序列号
- 截图后端收紧为 `scrcpy/auto`
- `tap` 失败时自动退化为极短 `swipe` 模拟点击

截图方案现状：

- 不再支持旧式 `adb screencap` 作为运行后端
- 依赖 `scrcpy-client` 持续拉取视频帧
- `screenshot_bgr()` 和 `screenshot_png()` 直接从 scrcpy 帧中取图

### 5.5 `image_matcher.py`

职责：OpenCV 模板匹配底层算法。

主要能力：

- 单模板最佳匹配
- 多目标匹配
- 匹配结果绘制与调试保存
- 支持从路径、字节流、数组读取图片

### 5.6 `local_ocr_util.py`

职责：RapidOCR 本地 OCR 封装。

当前主要承担两类任务：

1. 通用文字识别
2. 坐标识别

在坐标场景下，模块会先做裁剪、放大和增强，再识别并解析为 `(x, y)`。

### 5.7 `agent_service.py`

职责：大模型任务分发入口。

当前与打图链路直接相关的函数为：

- `extract_baotu_info(image)`
- `route_image_intent(image)`

其中 `extract_baotu_info(image)` 负责把游戏截图提交给 SiliconFlow 大模型，并要求返回 JSON：

```json
{
  "qiangdao_name": "强盗名称",
  "map_name": "地图名",
  "coord": [123, 456]
}
```

## 6. 识别策略设计

### 6.1 模板匹配

模板匹配主要用于：

- 地图按钮
- 地图关闭按钮
- 飞行符地图入口
- 道具栏按钮
- NPC 模板
- 对话模板
- 战斗按钮

优势：

- 对固定 UI 控件稳定
- 运行快，推理成本低

限制：

- 对分辨率、遮挡、亮度和 UI 状态变化敏感
- 对动态场景文本不如 OCR 灵活

### 6.2 本地 OCR

本地 OCR 主要用于：

- 查找“店小二”“挖宝图任务”等文本
- 查找目标强盗名称
- 识别当前位置坐标
- 识别地图名和战斗倒计时

当前 OCR 方案支持图像变体选择。业务层已经给“店小二”相关识别设置颜色策略：

- `店小二` -> `yellow_text`
- `挖宝图任务` -> `blue_purple_text`

这种设计把“业务规则”和“通用 OCR 能力”分离开了，便于后续扩展更多关键词颜色方案。

### 6.3 大模型识图

大模型识图只承担“语义抽取”任务，不直接负责点击执行。

当前用途：

- 从任务截图中提取强盗名称
- 从任务截图中提取地图名称
- 从任务截图中提取坐标

这种设计的优点是：

- 能处理较复杂的任务描述文本
- 能减少大量规则解析代码

需要注意的问题是：

- 依赖外部 API
- 解析质量受截图质量影响
- 地图名若与策略表不一致，会导致路由失败

## 7. 配置设计

### 7.1 配置原则

当前项目遵循统一配置入口原则，所有默认值和环境变量读取集中在 `bmad/botconfig.py`。

配置优先级为：

1. 当前进程环境变量
2. `.env`
3. `botconfig.py` 内默认值

### 7.2 核心配置类型

#### 基础运行配置

- `ADB_PATH`
- `ADB_SERIAL`
- `ANDROID_SCREENSHOT_BACKEND`
- `ANDROID_SCRCPY_MAX_FPS`
- `ANDROID_SCRCPY_BITRATE`
- `ANDROID_SCRCPY_CONNECTION_TIMEOUT_MS`

#### ROI 配置

- `MHXY_MAP_ROI`
- `ANDROID_COORD_ROI`
- `BATTLE_CALCULATION_ROI`

#### 地图与模板配置

- `ANDROID_TPL_MAP_BUTTON`
- `ANDROID_TPL_MAP_BUTTON_2`
- `ANDROID_TPL_MAP_GO`
- `ANDROID_TPL_MAP_EXIT`
- `ANDROID_TPL_MENU_DAOJU`
- `ANDROID_TPL_PROP_FEIXINGFU`
- `ANDROID_TPL_PROP_CHANGAN_FLAG`
- `ANDROID_TPL_MAP_TELEPORT_POINT`
- `ANDROID_TPL_BAOTU_RECEIVE_TASK`
- `ANDROID_TPL_BAOTU_ATTACK_TALK`
- `ANDROID_TPL_NPC_*`
- `ANDROID_TPL_SYSTEM_*`

#### 阈值配置

- `ANDROID_MATCH_THRESHOLD`
- `ANDROID_THR_MAP_BUTTON`
- `ANDROID_THR_MAP_GO`
- `ANDROID_THR_PROP_FEIXINGFU`
- `ANDROID_THR_PROP_CHANGAN_FLAG`
- `ANDROID_THR_MAP_TELEPORT_POINT`
- `ANDROID_THR_BAOTU_RECEIVE_TASK`
- `ANDROID_THR_NPC_XIAOER`
- `ANDROID_THR_SYSTEM_*`

#### 路线坐标配置

- `ZHUZI_TO_JINGWAI`
- `JINGWAI_TO_SHITUO`
- `CHANGAN_TO_HUANSHENG`
- `CHANGAN_FLY_YIZHANLAOBAN`
- `CHANGAN_FLY_YEWAI`
- `GUOJING_TO_PUTUO`
- `GUOJING_TO_DIFU`

#### 大模型配置

- `SILICONFLOW_API_KEY`
- `SILICONFLOW_BASE_URL`
- `SILICONFLOW_OCR_MODEL`
- `SILICONFLOW_QWEN_MODEL`

### 7.3 当前默认值中的关键信息

当前代码内可直接看到的关键默认值包括：

- `ANDROID_THR_NPC_XIAOER = 0.55`
- `ANDROID_THR_CHANGAN_HOTEL_DOOR = 0.3`
- `MHXY_MAP_ROI = "270,30,430,80"`
- `ANDROID_COORD_ROI = "249,82,418,127"`
- `SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"`
- `SILICONFLOW_OCR_MODEL = "PaddlePaddle/PaddleOCR-VL-1.5"`
- `SILICONFLOW_QWEN_MODEL = "Pro/moonshotai/Kimi-K2.6"`

## 8. 运行依赖

### 8.1 Python 与依赖

当前项目运行依赖主要包括：

- Python 3.10
- OpenCV
- numpy
- Pillow
- `scrcpy-client`
- `av==12.3.0`
- `rapidocr_onnxruntime`

### 8.2 外部环境依赖

- Android 设备已连接 ADB
- 游戏处于互通版可操作界面
- 模板图片资源完整
- 配置了可用的 SiliconFlow API Key

### 8.3 建议启动方式

在项目根目录执行：

```powershell
d:\PY_code\mhxy\mhxy_bot\.venv310\Scripts\python.exe run_datubot.py
```

如果当前终端已经激活虚拟环境，也可以执行：

```powershell
python run_datubot.py
```

## 9. 当前方案的关键特点

### 9.1 优点

- 采用纯函数化结构，模块边界相对清晰
- 模板匹配、本地 OCR、大模型识图三种能力分工明确
- 配置集中在 `botconfig.py`，便于统一维护
- 路线策略已经具备可扩展的地图分发表
- 坐标导航已支持游戏内数字键盘输入，适配性较强

### 9.2 当前已知限制

- 入口只执行单次打图，没有循环控制
- `go_to_xiaoer()` 仍依赖 NPC 模板匹配，尚未完全统一为 OCR 方案
- `route_by_map()` 仅支持已登记地图名，依赖 LLM 输出稳定
- `vision_bot.navigate_to_coord()` 里 `map_x.jpg`、`map_go.jpg` 仍是硬编码路径，未完全走配置常量
- 战斗逻辑较简单，只适用于基础场景
- 缺少统一状态机和失败恢复机制

## 10. 异常与失败点分析

### 10.1 接任务阶段

可能失败原因：

- 酒店入口模板未命中
- 店小二模板未命中
- OCR 未识别到“店小二”或“挖宝图任务”
- “领取任务”按钮未出现

当前应对方式：

- `receive_baotu_task()` 内部重试最多 3 次

### 10.2 路由阶段

可能失败原因：

- LLM 未识别出合法坐标
- 地图名不在已支持路由表中
- 路线入口坐标配置错误
- 飞行符、导标旗、NPC 模板未命中

### 10.3 战斗阶段

可能失败原因：

- OCR 未识别出目标强盗名称
- 名称颜色或显示区域变化
- 战斗倒计时 OCR 不稳定

## 11. 后续演进建议

建议按以下顺序继续演进：

1. 将 `go_to_xiaoer()` 改为纯 OCR 驱动，去掉对 NPC 模板的强依赖
2. 把 `navigate_to_coord()` 中硬编码模板路径统一迁移到 `botconfig.py`
3. 为 `route_by_map()` 增加地图名归一化映射，降低 LLM 输出抖动影响
4. 增加主循环调度能力，实现连续自动打图
5. 增加任务结果记录、异常截图和阶段状态落盘
6. 引入更稳定的状态机和失败回滚机制
7. 扩展战斗策略，支持更多宠物/人物技能逻辑

## 12. 总结

当前打图方案已经形成一条可运行的完整链路：

- 底层通过 ADB + scrcpy 完成设备交互和实时截图
- 中层通过模板匹配和本地 OCR 完成 UI 控件与文本定位
- 上层通过 SiliconFlow 大模型完成任务截图语义抽取
- 业务层通过 `datubot.py` 串起接任务、识图、跑图、攻击和战斗

从工程形态上看，这是一套“规则识别 + 视觉交互 + 大模型抽取”的混合自动化方案，适合当前梦幻西游互通版打图任务的自动执行场景。下一阶段的重点应放在稳定性、循环调度、状态恢复和 OCR 化统一上。
