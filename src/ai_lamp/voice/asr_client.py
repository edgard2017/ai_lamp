"""火山「豆包录音文件识别 2.0」语音转文本（ASR）客户端封装。

模型在字节云端跑；本模块只发 HTTPS 请求、拿回文本。任何能联网跑 Python 的机器都能用。

这是**录音文件识别标准版**（一段完整音频 → 文本），走"提交任务→轮询查询"的异步流程。
适合按键说话（push-to-talk）：录一段、松手、上传识别。实时流式识别是另一套接口，以后再加。

鉴权走**旧式** X-Api-App-Key + X-Api-Access-Key（该服务在独立 APP 下，非 TTS 的新版 API Key）：
  VOLC_ASR_APPID          APP ID（非机密）
  VOLC_ASR_ACCESS_TOKEN   Access Token（机密！只放 .env）
  VOLC_ASR_RESOURCE_ID    资源号，默认 volc.seedasr.auc（2.0 标准版）

用法：
    from ai_lamp.voice.asr_client import AsrClient
    client = AsrClient()
    print(client.recognize("outputs/audio/xxx.mp3"))
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from ..env import load_env

_ASR_BASE = "https://openspeech.bytedance.com/api/v3/auc/bigmodel"
_DEFAULT_RESOURCE_ID = "volc.seedasr.auc"


class AsrConfigError(RuntimeError):
    """缺少必要的 ASR 配置（APP ID / Access Token）时抛出。"""


class AsrError(RuntimeError):
    """识别失败（服务端返回错误码）时抛出。"""


class AsrClient:
    """对火山录音文件识别标准版的薄封装：上传一段音频，返回识别文本。"""

    def __init__(
        self,
        appid: Optional[str] = None,
        access_token: Optional[str] = None,
        resource_id: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        load_env()
        self.appid = appid or os.environ.get("VOLC_ASR_APPID")
        self.access_token = access_token or os.environ.get("VOLC_ASR_ACCESS_TOKEN")
        self.resource_id = (
            resource_id
            or os.environ.get("VOLC_ASR_RESOURCE_ID", _DEFAULT_RESOURCE_ID)
        )
        self.timeout = timeout

        if not self.appid or not self.access_token:
            raise AsrConfigError(
                "缺少 VOLC_ASR_APPID / VOLC_ASR_ACCESS_TOKEN。请在 .env 填入 ASR 服务的凭证。"
            )

    def _headers(self, task_id: str, extra: Optional[dict] = None) -> dict:
        h = {
            "X-Api-App-Key": self.appid,
            "X-Api-Access-Key": self.access_token,
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Request-Id": task_id,
            "X-Api-Sequence": "-1",
            "Content-Type": "application/json",
        }
        if extra:
            h.update(extra)
        return h

    def recognize(
        self,
        audio_path: str,
        *,
        enable_punc: bool = True,
        poll_interval: float = 1.0,
        max_polls: int = 30,
    ) -> str:
        """识别 audio_path（mp3/wav/ogg）里的语音，返回文本。

        标准版是异步：submit 提交任务 → query 轮询直到完成。
        """
        import requests  # 延迟导入

        b64 = base64.b64encode(Path(audio_path).read_bytes()).decode("utf-8")
        task_id = str(uuid.uuid4())

        sub = requests.post(
            _ASR_BASE + "/submit",
            headers=self._headers(task_id),
            json={
                "user": {"uid": self.appid},
                "audio": {"data": b64},
                "request": {"model_name": "bigmodel", "enable_punc": enable_punc},
            },
            timeout=self.timeout,
        )
        sub_code = sub.headers.get("X-Api-Status-Code")
        if sub_code != "20000000":
            raise AsrError(
                f"提交失败 code={sub_code} msg={sub.headers.get('X-Api-Message')}"
            )
        logid = sub.headers.get("X-Tt-Logid", "")

        for _ in range(max_polls):
            q = requests.post(
                _ASR_BASE + "/query",
                headers=self._headers(task_id, {"X-Tt-Logid": logid}),
                data=json.dumps({}),
                timeout=self.timeout,
            )
            code = q.headers.get("X-Api-Status-Code")
            if code == "20000000":  # 完成
                return q.json().get("result", {}).get("text", "")
            if code in ("20000001", "20000002"):  # 处理中 / 排队
                time.sleep(poll_interval)
                continue
            raise AsrError(
                f"查询失败 code={code} msg={q.headers.get('X-Api-Message')}"
            )

        raise AsrError("识别超时（轮询次数用尽仍未完成）")
