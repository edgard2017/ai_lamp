"""火山「豆包语音」文本转语音（TTS）客户端封装。

模型在字节云端跑；本模块只发 HTTPS 请求、拿回音频。任何能联网跑 Python 的机器
（开发服务器 / 树莓派）都能用。

鉴权走**新版控制台 API Key**（X-Api-Key），不需要旧版 Access Token。经实测：
  V3 单向流式 SSE 接口 + 资源号 volc.tts.default + BV 系列音色 → 可用。

配置一律从环境变量读，绝不硬编码、绝不入库：
  VOLC_SPEECH_APIKEY    新版 API Key（机密）
  VOLC_TTS_VOICE        音色代号，默认 BV007_streaming
  VOLC_TTS_RESOURCE_ID  资源号，默认 volc.tts.default

用法：
    from ai_lamp.voice.tts_client import TtsClient
    client = TtsClient()
    path = client.synthesize("你好呀，我是你的学习小台灯。", "outputs/audio/hi.mp3")
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from ..env import load_env

_TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional/sse"
_DEFAULT_VOICE = "BV007_streaming"
_DEFAULT_RESOURCE_ID = "volc.tts.default"


class TtsConfigError(RuntimeError):
    """缺少必要的语音配置（API Key 等）时抛出。"""


class TtsError(RuntimeError):
    """合成失败（服务端返回错误码）时抛出。"""


class TtsClient:
    """对火山 V3 单向流式 TTS 的薄封装：一次输入文本，收齐音频再返回。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice: Optional[str] = None,
        resource_id: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        load_env()
        self.api_key = api_key or os.environ.get("VOLC_SPEECH_APIKEY")
        self.voice = voice or os.environ.get("VOLC_TTS_VOICE", _DEFAULT_VOICE)
        self.resource_id = (
            resource_id
            or os.environ.get("VOLC_TTS_RESOURCE_ID", _DEFAULT_RESOURCE_ID)
        )
        self.timeout = timeout

        if not self.api_key:
            raise TtsConfigError(
                "缺少 VOLC_SPEECH_APIKEY。请在 .env 填入新版控制台的 API Key。"
            )

    def synthesize(
        self,
        text: str,
        out_path: str,
        *,
        audio_format: str = "mp3",
        sample_rate: int = 24000,
        speech_rate: int = 0,
    ) -> str:
        """把 text 合成为音频写到 out_path，返回该路径。

        text        待合成文本（<300 字为宜，上限 1024 字节）
        out_path    输出文件路径（扩展名应与 audio_format 一致）
        audio_format mp3 / pcm / ogg_opus
        speech_rate  语速 [-50,100]，0 为原速，100 约两倍速
        """
        import requests  # 延迟导入，避免无网/未装依赖时影响其它模块

        headers = {
            "X-Api-Key": self.api_key,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": str(uuid.uuid4()),
            "Content-Type": "application/json",
        }
        payload = {
            "user": {"uid": "ai_lamp"},
            "req_params": {
                "text": text,
                "speaker": self.voice,
                "audio_params": {
                    "format": audio_format,
                    "sample_rate": sample_rate,
                    "speech_rate": speech_rate,
                },
            },
        }

        resp = requests.post(
            _TTS_URL, headers=headers, json=payload, stream=True, timeout=self.timeout
        )
        if resp.status_code != 200:
            raise TtsError(f"HTTP {resp.status_code}: {resp.text[:200]}")

        audio = bytearray()
        final_code = None
        final_msg = ""
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            try:
                obj = json.loads(raw[5:].strip())
            except json.JSONDecodeError:
                continue
            chunk = obj.get("data")
            if isinstance(chunk, str) and chunk:
                audio.extend(base64.b64decode(chunk))
            if "code" in obj:
                final_code = obj.get("code")
                final_msg = obj.get("message", "")

        # 20000000 = 合成完成；有音频即视为成功
        if not audio:
            raise TtsError(f"未取回音频（code={final_code} msg={final_msg}）")

        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(bytes(audio))
        return str(out)
