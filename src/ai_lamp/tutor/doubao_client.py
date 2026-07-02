"""豆包（火山引擎·方舟，OpenAI 兼容）客户端封装。

模型在字节云端运行；本模块只发 HTTPS 请求、收结果。任何能联网跑 Python 的机器
（开发服务器 / 树莓派，x86 / ARM 都行）都能用。

鉴权与配置一律从**环境变量**读，绝不硬编码、绝不入库：
  ARK_API_KEY   你的火山引擎 API Key（机密！只在终端 export，别贴进聊天/代码）
  ARK_MODEL     推理接入点 id（形如 ep-xxxxxxxx 或模型名；非机密）
  ARK_BASE_URL  可选，默认 https://ark.cn-beijing.volces.com/api/v3

用法：
    from ai_lamp.tutor.doubao_client import DoubaoClient
    client = DoubaoClient()
    print(client.ask("用一句话鼓励一个刚做错数学题的小朋友"))
"""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from typing import List, Optional

_DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


class DoubaoConfigError(RuntimeError):
    """缺少必要的环境变量配置时抛出。"""


class DoubaoClient:
    """对豆包 chat.completions 的薄封装，支持纯文本与「看图」两种调用。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("ARK_API_KEY")
        self.model = model or os.environ.get("ARK_MODEL")
        self.base_url = base_url or os.environ.get("ARK_BASE_URL", _DEFAULT_BASE_URL)
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.api_key:
            raise DoubaoConfigError(
                "缺少 ARK_API_KEY。请在终端执行： export ARK_API_KEY=你的key"
                "（别把 key 贴进聊天或代码）"
            )
        if not self.model:
            raise DoubaoConfigError(
                "缺少 ARK_MODEL（推理接入点 id）。请执行： export ARK_MODEL=ep-xxxx"
            )

        from openai import OpenAI  # 懒加载，未用到豆包时无需装 SDK

        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
        )

    def ask(
        self,
        text: str,
        image_path: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """发一条消息，返回模型回复文本。

        text       用户消息（如题目描述或引导指令）
        image_path 可选，作业照片路径；提供则走多模态（接入点需支持视觉）
        system     可选，系统提示（设定角色/语气，如"循循善诱的小学辅导老师"）
        """
        content: object
        if image_path:
            content = [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": _encode_image(image_path)}},
            ]
        else:
            content = text

        messages: List[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:  # noqa: BLE001 - 统一重试，最后再抛
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"调用豆包失败（重试 {self.max_retries} 次后）：{last_exc}")


def _encode_image(path: str) -> str:
    """把本地图片编码成 data URL，供多模态消息使用。"""
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"
