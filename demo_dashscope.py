import os
from http import HTTPStatus

import dashscope
from dashscope import Generation


def main() -> None:
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("未检测到 DASHSCOPE_API_KEY。请先设置：")
        print('  export DASHSCOPE_API_KEY="YOUR_KEY_HERE"')
        return

    dashscope.base_http_api_url = os.environ.get(
        "DASHSCOPE_API_BASE", "https://dashscope-intl.aliyuncs.com/api/v1"
    )

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "用三条要点简述此项目目录的用途。"},
    ]

    resp = Generation.call(
        api_key=api_key,
        model="qwen-plus",
        messages=messages,
        result_format="message",
    )
    if resp.status_code == HTTPStatus.OK:
        print(resp)
    else:
        print(
            f"请求失败: status_code={resp.status_code}, code={resp.code}, message={resp.message}"
        )


if __name__ == "__main__":
    main()
