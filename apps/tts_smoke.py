#!/usr/bin/env python3
"""TTS 冒烟测试：把一句话合成成音频文件，验证「台灯能开口说话」。

用法：
    python3 apps/tts_smoke.py                      # 合成默认问候语
    python3 apps/tts_smoke.py "自己想说的话"        # 合成指定文本

输出到 outputs/audio/ 下。开发机上可下载试听；树莓派上直接 aplay/mpg123 播放。
"""

import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.voice.tts_client import TtsClient, TtsConfigError, TtsError  # noqa: E402


def main() -> int:
    text = sys.argv[1] if len(sys.argv) > 1 else "你好呀，我是你的学习小台灯。今天我们一起加油，好不好？"

    try:
        client = TtsClient()
    except TtsConfigError as exc:
        print(f"配置错误：{exc}")
        return 2

    out_path = os.path.join(_REPO_ROOT, "outputs", "audio", "tts_smoke.mp3")
    print(f"音色={client.voice}  资源号={client.resource_id}")
    print(f"合成：{text}")

    t0 = time.time()
    try:
        path = client.synthesize(text, out_path)
    except TtsError as exc:
        print(f"合成失败：{exc}")
        return 1
    dt = time.time() - t0

    size = os.path.getsize(path)
    print(f"✓ 成功  {size/1024:.1f} KB  用时 {dt:.2f}s")
    print(f"文件：{path}")
    print("试听：开发机可下载；树莓派上  mpg123 " + path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
