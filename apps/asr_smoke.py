#!/usr/bin/env python3
"""ASR 冒烟测试：验证「台灯能听懂话」。

没有麦克风也能测——用 TTS 先合成一句话当输入，喂给 ASR 看能不能识别回来
（TTS 当嘴、ASR 当耳朵，让台灯说给自己听）。

用法：
    python3 apps/asr_smoke.py                       # TTS 合成默认句子再识别
    python3 apps/asr_smoke.py "自定义要念的话"        # 换一句
    python3 apps/asr_smoke.py --file path/to.mp3    # 直接识别已有音频（如真人录音）
"""

import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.voice.asr_client import AsrClient, AsrConfigError, AsrError  # noqa: E402
from ai_lamp.voice.tts_client import TtsClient, TtsConfigError, TtsError  # noqa: E402


def main() -> int:
    audio_path = None
    sentence = "今天天气很好，我们一起来做数学作业吧。"

    args = sys.argv[1:]
    if args and args[0] == "--file":
        if len(args) < 2:
            print("用法：python3 apps/asr_smoke.py --file 音频路径")
            return 2
        audio_path = args[1]
    elif args:
        sentence = args[0]

    try:
        asr = AsrClient()
    except AsrConfigError as exc:
        print(f"配置错误：{exc}")
        return 2

    # 没给现成音频就用 TTS 合成一段
    if audio_path is None:
        try:
            tts = TtsClient()
        except TtsConfigError as exc:
            print(f"TTS 配置错误：{exc}")
            return 2
        audio_path = os.path.join(_REPO_ROOT, "outputs", "audio", "asr_input.mp3")
        print(f"[TTS] 合成输入音频：{sentence}")
        try:
            tts.synthesize(sentence, audio_path)
        except TtsError as exc:
            print(f"TTS 合成失败：{exc}")
            return 1

    print(f"[ASR] 识别中… 资源号={asr.resource_id}")
    t0 = time.time()
    try:
        text = asr.recognize(audio_path)
    except AsrError as exc:
        print(f"识别失败：{exc}")
        return 1
    dt = time.time() - t0

    print(f"✓ 完成  用时 {dt:.2f}s")
    if sentence and audio_path.endswith("asr_input.mp3"):
        print(f"原文：{sentence}")
    print(f"识别：{text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
