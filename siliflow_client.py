import argparse  # 命令行参数解析
import base64  # base64 编解码
import json  # JSON 序列化与反序列化
import os  # 文件路径与环境变量
import sys  # 进程参数与退出码
import socket
import urllib.error  # urllib 的异常类型
import urllib.request  # 发起 HTTP 请求
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union  # 类型标注
import botconfig
import sys_util
import cv2
import numpy as np

def _guess_mime_type(filename: str) -> str:  # 根据文件扩展名猜测图片 MIME 类型
    ext = os.path.splitext(filename.lower())[1]  # 提取扩展名并转小写
    if ext in (".jpg", ".jpeg"):  # JPEG 图片
        return "image/jpeg"  # 返回对应 MIME
    if ext == ".webp":  # WebP 图片
        return "image/webp"  # 返回对应 MIME
    if ext == ".gif":  # GIF 图片
        return "image/gif"  # 返回对应 MIME
    return "image/png"  # 兜底按 PNG 处理


def _image_to_data_url(image: Union[str, bytes, bytearray, memoryview, np.ndarray], mime_type: Optional[str] = None) -> str:  # 图片转 data URL
    if isinstance(image, str):  # 入参是文件路径
        img_path = os.path.abspath(image)  # 转为绝对路径
        with open(img_path, "rb") as f:  # 以二进制读取图片文件
            data = f.read()  # 读出全部字节
        mime = mime_type or _guess_mime_type(img_path)  # 优先使用显式 mime，否则按扩展名猜测
    elif isinstance(image, np.ndarray):
        img = image
        if not img.flags["C_CONTIGUOUS"]:
            img = np.ascontiguousarray(img)
        ok, buf = cv2.imencode(".png", img)
        if not ok:
            raise RuntimeError("图片编码失败（cv2.imencode .png）")
        data = buf.tobytes()
        mime = mime_type or "image/png"
    else:  # 入参是原始 bytes
        data = image  # 直接使用传入字节
        mime = mime_type or "image/png"  # bytes 场景默认按 PNG
    b64 = base64.b64encode(data).decode("ascii")  # 图片 bytes 做 base64 并转成字符串
    return f"data:{mime};base64,{b64}"  # 拼成 data URL（可直接喂给多模态接口）


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_s: float) -> Dict[str, Any]:  # POST JSON 并解析 JSON 响应
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")  # 将 payload 序列化为 UTF-8 JSON 字节
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")  # 构造 HTTP POST 请求
    try:  # 捕获网络请求异常
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # 发送请求并拿到响应
            raw = resp.read().decode("utf-8", errors="replace")  # 读取响应体并按 UTF-8 解码
            return json.loads(raw) if raw else {}  # 有内容则解析 JSON，否则返回空 dict
    except urllib.error.HTTPError as e:  # 服务端返回非 2xx
        raw = ""  # 用于保存错误响应体
        try:  # 尝试读取错误响应体
            raw = e.read().decode("utf-8", errors="replace")  # 解码错误响应体
        except Exception:  # 读取错误体也失败
            raw = ""  # 回退为空字符串
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {raw}".strip()) from e  # 抛出带上下文的异常
    except urllib.error.URLError as e:  # 网络层错误（DNS/连接失败等）
        raise RuntimeError(f"请求失败: {e.reason}") from e  # 抛出统一的运行时错误
    except (socket.timeout, TimeoutError) as e:
        raise RuntimeError("请求超时") from e


def _strip_json_fence(text: str) -> str:  # 去掉 LLM 常见的 ```json ... ``` 围栏，便于解析
    s = text.strip()  # 先做整体去空白
    if s.startswith("```"):  # 以代码块围栏开头
        lines = s.splitlines()  # 按行拆分
        if len(lines) >= 2 and lines[0].startswith("```"):  # 第一行是 ``` 或 ```json
            lines = lines[1:]  # 去掉第一行围栏
        if lines and lines[-1].strip() == "```":  # 最后一行是 ```
            lines = lines[:-1]  # 去掉最后一行围栏
        s = "\n".join(lines).strip()  # 重新拼回正文并去空白
        if s.lower().startswith("json"):  # 某些输出会变成首行 "json"
            s = s[4:].lstrip()  # 去掉 "json" 前缀
    return s  # 返回清理后的文本


def _try_parse_json(text: str) -> Optional[Any]:  # 尝试把文本解析为 JSON，失败则返回 None
    s = _strip_json_fence(text)  # 先去掉可能的 JSON 围栏
    try:  # 捕获 JSON 解析异常
        return json.loads(s)  # 返回解析后的对象（dict/list/str/number/...）
    except Exception:  # 解析失败
        return None  # 返回 None 表示不可解析


def siliconflow_chat_completions(  # 调用 SiliconFlow 的 /chat/completions 接口
    model: str,  # 模型名称
    messages: Sequence[Dict[str, Any]],  # OpenAI 风格 messages
    temperature: float = 0.0,  # 采样温度
    max_tokens: int = 2048,  # 最大输出 token
    timeout_s: float = 120.0,  # 请求超时时间（秒）
    extra: Optional[Dict[str, Any]] = None,  # 额外透传字段（如 response_format 等）
) -> Dict[str, Any]:  # 返回 API 的 JSON 响应 dict
    api_key = botconfig.env_str("SILICONFLOW_API_KEY", botconfig.SILICONFLOW_API_KEY)  # 读取/覆盖 API Key
    if not api_key:  # 没有拿到有效 key
        raise RuntimeError("缺少 SILICONFLOW_API_KEY，请在环境变量或 .env 中配置")  # 直接报错

    base_url = botconfig.env_str("SILICONFLOW_BASE_URL", botconfig.SILICONFLOW_BASE_URL).rstrip("/")  # 读取/覆盖 base_url
    url = f"{base_url}/chat/completions"  # 拼接 chat completions 端点

    payload: Dict[str, Any] = {  # 组装请求体
        "model": model,  # 模型名
        "messages": list(messages),  # messages 转为 list，确保可 JSON 序列化
        "temperature": temperature,  # 采样温度
        "max_tokens": max_tokens,  # 最大输出 token
    }  # payload 结束
    if extra:  # 如果提供了额外字段
        payload.update(extra)  # 合并到 payload（会覆盖同名字段）

    headers = {  # HTTP 请求头
        "Authorization": f"Bearer {api_key}",  # Bearer Token 认证
        "Content-Type": "application/json",  # JSON 请求体
    }  # headers 结束
    effective_timeout = botconfig.env_float("SILICONFLOW_TIMEOUT_S", float(timeout_s))
    return _post_json(url, payload, headers=headers, timeout_s=effective_timeout)  # 发送请求并返回响应


def siliconflow_paddleocr(  # 用 PaddleOCR-VL 作为多模态 OCR：输入图片，输出文本
    image: Union[str, bytes],  # 图片路径或图片 bytes
) -> Dict[str, Any]:  # 返回包含 content/parsed/raw_response 的结果 dict
    model = botconfig.env_str("SILICONFLOW_OCR_MODEL", botconfig.SILICONFLOW_OCR_MODEL)  # 选择 OCR 模型
    data_url = _image_to_data_url(image)  # 图片转为 data URL（多模态输入格式）
    # _ = prompt  # 显式忽略 prompt，避免未使用变量告警
    prompt_text = "对图片做OCR识别。直接输出识别到的文字（纯文本），不要输出JSON或其它解释。"  # 约束输出为纯文本
    messages = [  # 构造 chat messages
        {  # 单轮 user 消息
            "role": "user",  # 消息角色
            "content": [  # 多模态 content 列表
                {  # 文本片段
                    "type": "text",  # content 类型：文本
                    "text": prompt_text,  # OCR 指令
                },  # 文本片段结束
                {"type": "image_url", "image_url": {"url": data_url}},  # 图片片段（data URL）
            ],  # content 结束
        }  # user 消息结束
    ]  # messages 结束

    resp = siliconflow_chat_completions(  # 调用统一的 chat completions 封装
        model=model,  # 传入模型名
        messages=messages,  # 传入 messages
    )  # 请求结束
    content = ""  # 用于保存模型输出文本
    try:  # 尝试从响应中取出 message.content
        content = resp["choices"][0]["message"]["content"] or ""  # 兼容为空的情况
    except Exception:  # 响应结构异常或字段缺失
        content = ""  # 回退为空字符串
    parsed = _try_parse_json(content) if content else None  # 若输出意外是 JSON，尝试解析（否则为 None）
    return {"model": model, "content": content, "parsed": parsed, "raw_response": resp}  # 返回统一结构


def siliconflow_qwen_structured(  # 用 Qwen-VL 做结构化输出：输入图片 + 提示词，输出 JSON
    image: Union[str, bytes],  # 图片路径或图片 bytes
    prompt: str,  # 用户提示词（描述要提取的信息）
    schema: Optional[Dict[str, Any]] = None,  # 可选 JSON Schema（约束输出结构）
    enable_thinking: Optional[bool] = None,
    ) -> Dict[str, Any]:  # 返回包含 content/parsed/raw_response 的结果 dict
    model = botconfig.env_str("SILICONFLOW_QWEN_MODEL", botconfig.SILICONFLOW_QWEN_MODEL)  # 选择 VL 模型
    data_url = _image_to_data_url(image)  # 图片转为 data URL

    schema_text = ""  # 用于拼接 schema 约束文本
    if schema is not None:  # 传入 schema 时
        schema_text = "\n你必须严格按以下JSON Schema输出：\n" + json.dumps(schema, ensure_ascii=False)  # 把 schema 作为文本加入提示

    messages = [  # 构造 chat messages
        {  # 单轮 user 消息
            "role": "user",  # 消息角色
            "content": [  # 多模态 content 列表
                {  # 文本片段
                    "type": "text",  # content 类型：文本
                    "text": prompt.strip() + "\n\n只返回JSON，不要输出其它文字。" + schema_text,  # 约束只输出 JSON，并附带 schema 约束
                },  # 文本片段结束
                {"type": "image_url", "image_url": {"url": data_url}},  # 图片片段（data URL）
            ],  # content 结束
        }  # user 消息结束
    ]  # messages 结束

    if enable_thinking is None:
        enable_thinking = botconfig.env_bool("SILICONFLOW_ENABLE_THINKING", default=False)

    resp = siliconflow_chat_completions(  # 调用统一的 chat completions 封装
        model=model,  # 传入模型名
        messages=messages,  # 传入 messages
        extra={"enable_thinking": bool(enable_thinking)},
    )  # 请求结束
    content = ""  # 用于保存模型输出文本
    try:  # 尝试从响应中取出 message.content
        content = resp["choices"][0]["message"]["content"] or ""  # 兼容为空的情况
    except Exception:  # 响应结构异常或字段缺失
        content = ""  # 回退为空字符串
    parsed = _try_parse_json(content) if content else None  # 尝试把输出解析为 JSON
    return {"model": model, "content": content, "parsed": parsed, "raw_response": resp}  # 返回统一结构

def paddleocr(image: Union[str, bytes]) -> Dict[str, Any]:
    result = siliconflow_paddleocr(image)
      # 调用 PaddleOCR-VL 模型识别
    return result['content']


# sys_util.load_dotenv()
# result = paddleocr("debug_capture/20260501_195332_detected414_308_474_368.png.png")
# print(result)
