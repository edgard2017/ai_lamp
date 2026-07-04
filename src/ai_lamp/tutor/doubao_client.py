"""豆包（火山引擎·方舟，OpenAI 兼容）客户端封装。

模型在字节云端运行；本模块只用 requests 发 HTTPS 请求、收结果，**不依赖 openai SDK**。
任何能联网跑 Python 的机器（开发服务器 / 树莓派，x86 / ARM、老 Python 3.7 都行）都能用。

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

from ..env import load_env

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
        deep_thinking: bool = False,
    ) -> None:
        # 项目启动时自动读取 .env（若存在）；已 export 的真实环境变量优先，不被覆盖
        load_env()
        self.api_key = api_key or os.environ.get("ARK_API_KEY")
        self.model = model or os.environ.get("ARK_MODEL")
        self.base_url = base_url or os.environ.get("ARK_BASE_URL", _DEFAULT_BASE_URL)
        self.timeout = timeout
        self.max_retries = max_retries
        # 默认关掉「深度思考」：seed 系模型默认会先长篇推理（慢一倍），
        # 台灯场景要的是快。需要更高准确度时再 deep_thinking=True 打开。
        self._extra_body = {} if deep_thinking else {"thinking": {"type": "disabled"}}

        if not self.api_key:
            raise DoubaoConfigError(
                "缺少 ARK_API_KEY。请在终端执行： export ARK_API_KEY=你的key"
                "（别把 key 贴进聊天或代码）"
            )
        if not self.model:
            raise DoubaoConfigError(
                "缺少 ARK_MODEL（推理接入点 id）。请执行： export ARK_MODEL=ep-xxxx"
            )

        # 走 requests 直连 ARK 的 OpenAI 兼容 REST 接口，不依赖 openai SDK，
        # 这样老 Python（3.7）和树莓派上零额外依赖即可运行。
        self._chat_url = self.base_url.rstrip("/") + "/chat/completions"

    def ask(
        self,
        text: str,
        image_path: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """发一条消息，返回模型回复文本。

        text       用户消息（如题目描述或引导指令）
        image_path 可选，作业照片路径；提供则走多模态（接入点需支持视觉）
        system     可选，系统提示（设定角色/语气，如"循循善诱的小学辅导老师"）
        max_tokens 可选，限制回复长度
        """
        messages: List[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(user_message(text, image_path))
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """多轮对话：传入完整消息历史，返回模型回复文本。

        模型本身无状态——"记忆"靠调用方维护这份 messages 列表：每轮把用户新话和
        模型回复依次 append 进去，再整份递进来。第一条可含 system，图片放在首条
        user 消息里即可（见 user_message）。
        """
        import requests  # 延迟导入，避免无网/未装依赖时影响其它模块

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(self._extra_body)  # 如 thinking:disabled 合并进请求体

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.post(
                    self._chat_url, headers=headers, json=payload, timeout=self.timeout
                )
            except Exception as exc:  # noqa: BLE001 - 网络层错误可重试
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                continue

            if resp.status_code == 200:
                data = resp.json()
                return (data["choices"][0]["message"]["content"] or "").strip()

            # 4xx（鉴权/参数/模型不存在）重试无益，直接抛出便于定位
            if 400 <= resp.status_code < 500:
                raise RuntimeError(
                    f"豆包请求被拒 HTTP {resp.status_code}: {resp.text[:300]}"
                )

            # 5xx 等服务端错误，可重试
            last_exc = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            if attempt < self.max_retries:
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"调用豆包失败（重试 {self.max_retries} 次后）：{last_exc}")


def user_message(text: str, image_path: Optional[str] = None) -> dict:
    """构造一条 user 消息。给了 image_path 就走多模态（文本 + 图片 data URL）。"""
    if image_path:
        content: object = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": _encode_image(image_path)}},
        ]
    else:
        content = text
    return {"role": "user", "content": content}


def _encode_image(path: str) -> str:
    """把本地图片编码成 data URL，供多模态消息使用。"""
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "image/jpeg"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"
