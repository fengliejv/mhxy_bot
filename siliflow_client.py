import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        return


def _guess_mime_type(filename: str) -> str:
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    if ext == ".gif":
        return "image/gif"
    return "image/png"


def _image_to_data_url(image: Union[str, bytes], mime_type: Optional[str] = None) -> str:
    if isinstance(image, str):
        img_path = os.path.abspath(image)
        with open(img_path, "rb") as f:
            data = f.read()
        mime = mime_type or _guess_mime_type(img_path)
    else:
        data = image
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
    *,
    model: str,
    messages: Sequence[Dict[str, Any]],
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout_s: float = 60.0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    api_key = api_key or os.getenv("SILICONFLOW_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("缺少 SILICONFLOW_API_KEY，请在环境变量或 .env 中配置")

    base_url = (base_url or os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")).rstrip("/")
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
    return _post_json(url, payload, headers=headers, timeout_s=timeout_s)


def siliconflow_paddleocr(
    image: Union[str, bytes],
    *,
    prompt: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_s: float = 60.0,
    max_tokens: int = 2048,
) -> Dict[str, Any]:
    model = model or os.getenv("SILICONFLOW_OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.5")
    data_url = _image_to_data_url(image)
    _ = prompt
    prompt_text = "对图片做OCR识别。直接输出识别到的文字（纯文本），不要输出JSON或其它解释。"
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt_text,
                },
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    resp = siliconflow_chat_completions(
        model=model,
        messages=messages,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
    )
    content = ""
    try:
        content = resp["choices"][0]["message"]["content"] or ""
    except Exception:
        content = ""
    parsed = _try_parse_json(content) if content else None
    return {"model": model, "content": content, "parsed": parsed, "raw_response": resp}


def siliconflow_qwen_structured(
    image: Union[str, bytes],
    prompt: str,
    *,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    schema: Optional[Dict[str, Any]] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout_s: float = 60.0,
) -> Dict[str, Any]:
    model = model or os.getenv("SILICONFLOW_QWEN_MODEL", "Qwen/Qwen3.6-VL-Plus")
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

    resp = siliconflow_chat_completions(
        model=model,
        messages=messages,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_s=timeout_s,
    )
    content = ""
    try:
        content = resp["choices"][0]["message"]["content"] or ""
    except Exception:
        content = ""
    parsed = _try_parse_json(content) if content else None
    return {"model": model, "content": content, "parsed": parsed, "raw_response": resp}


def main(argv: List[str]) -> int:
    _load_dotenv()

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ocr = sub.add_parser("ocr")
    p_ocr.add_argument("--image", required=True)
    p_ocr.add_argument("--prompt", default="")
    p_ocr.add_argument("--model", default="")
    p_ocr.add_argument("--max-tokens", type=int, default=2048)
    p_ocr.add_argument("--timeout", type=float, default=60.0)

    p_vl = sub.add_parser("qwen")
    p_vl.add_argument("--image", required=True)
    p_vl.add_argument("--prompt", required=True)
    p_vl.add_argument("--model", default="")
    p_vl.add_argument("--temperature", type=float, default=0.0)
    p_vl.add_argument("--max-tokens", type=int, default=2048)
    p_vl.add_argument("--timeout", type=float, default=60.0)

    args = parser.parse_args(argv)

    if args.cmd == "ocr":
        result = siliconflow_paddleocr(
            args.image,
            prompt=args.prompt.strip() or None,
            model=args.model.strip() or None,
            max_tokens=args.max_tokens,
            timeout_s=args.timeout,
        )
        print(json.dumps(result["parsed"] if result["parsed"] is not None else result, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "qwen":
        result = siliconflow_qwen_structured(
            args.image,
            args.prompt,
            model=args.model.strip() or None,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_s=args.timeout,
        )
        print(json.dumps(result["parsed"] if result["parsed"] is not None else result, ensure_ascii=False, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
