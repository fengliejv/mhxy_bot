import base64
import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np

from .core import config as botconfig
from .core.common import image_io


def _guess_mime_type(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "image/png"


def _image_to_data_url(image: Union[str, bytes, bytearray, memoryview, np.ndarray], mime_type: Optional[str] = None) -> str:
    if isinstance(image, str):
        img_path = os.path.abspath(image)
        with open(img_path, "rb") as f:
            data = f.read()
        mime = mime_type or _guess_mime_type(img_path)
    else:
        data = image_io.to_png_bytes(image)
        mime = mime_type or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str], timeout_s: float) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        raise RuntimeError(f"HTTP {e.code} {e.reason}: {raw}".strip()) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"请求失败: {e.reason}") from e
    except (socket.timeout, TimeoutError) as e:
        raise RuntimeError("请求超时") from e


def _strip_json_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
    return s


def _try_parse_json(text: str) -> Optional[Any]:
    s = _strip_json_fence(text)
    try:
        return json.loads(s)
    except Exception:
        return None


def siliconflow_chat_completions(
    model: str,
    messages: Sequence[Dict[str, Any]],
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout_s: float = 120.0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_key = botconfig.SILICONFLOW_API_KEY
    if not api_key:
        raise RuntimeError(f"缺少 {botconfig.KEY_SILICONFLOW_API_KEY}，请在环境变量或 .env 中配置")

    base_url = botconfig.SILICONFLOW_BASE_URL.rstrip("/")
    url = f"{base_url}/chat/completions"

    payload: Dict[str, Any] = {
        "model": model,
        "messages": list(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra:
        payload.update(extra)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    effective_timeout = botconfig.siliconflow_effective_timeout_s(timeout_s)
    return _post_json(url, payload, headers=headers, timeout_s=effective_timeout)


def siliconflow_qwen_structured(
    image: Union[str, bytes, bytearray, memoryview, np.ndarray],
    prompt: str,
    schema: Optional[Dict[str, Any]] = None,
    enable_thinking: Optional[bool] = None,
) -> Dict[str, Any]:
    model = botconfig.SILICONFLOW_QWEN_MODEL
    data_url = _image_to_data_url(image)

    schema_text = ""
    if schema is not None:
        schema_text = "\n你必须严格按以下JSON Schema输出：\n" + json.dumps(schema, ensure_ascii=False)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt.strip() + "\n\n只返回JSON，不要输出其它文字。" + schema_text,
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    if enable_thinking is None:
        enable_thinking = botconfig.SILICONFLOW_ENABLE_THINKING

    resp = siliconflow_chat_completions(
        model=model,
        messages=messages,
        extra={"enable_thinking": bool(enable_thinking)},
    )
    content = ""
    try:
        content = resp["choices"][0]["message"]["content"] or ""
    except Exception:
        content = ""
    parsed = _try_parse_json(content) if content else None
    return {"model": model, "content": content, "parsed": parsed, "raw_response": resp}
