#!/usr/bin/env python3
"""坐姿检测演示：拍一张照片 → 发给豆包多模态大模型 → 说出坐姿是否 OK。

这条路**不需要** mediapipe/cv2，Pi3 现在就能跑：Pi 只负责拍照，识别在云端。
下周摄像头到位后，在树莓派上：
    python3 apps/posture_check.py                    # 拍照并检测坐姿
    python3 apps/posture_check.py --file some.jpg    # 用已有照片检测（不拍照）
    python3 apps/posture_check.py --speak            # 检测后把提醒用 TTS 说出来

依赖 .env 里的 ARK_*（多模态模型）配置；--speak 还需 VOLC_SPEECH_* 配置。
"""

import argparse
import json
import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.tutor.doubao_client import DoubaoClient, DoubaoConfigError  # noqa: E402
from ai_lamp.tutor.prompts import POSTURE_SYSTEM  # noqa: E402


def _parse_reply(reply: str) -> dict:
    """模型返回的 JSON 文本 → dict；容错去掉可能的 ```json 包裹。"""
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text.strip())
    except Exception:
        return {"posture_ok": None, "issues": [], "advice": reply.strip()}


def main() -> int:
    ap = argparse.ArgumentParser(description="拍照 + 豆包多模态坐姿检测")
    ap.add_argument("--file", help="用已有照片而不是现拍")
    ap.add_argument("--speak", action="store_true", help="把提醒用 TTS 说出来")
    args = ap.parse_args()

    # 1) 取一张照片（现拍或用已有文件）
    if args.file:
        photo = args.file
        if not os.path.exists(photo):
            print(f"照片不存在：{photo}")
            return 2
    else:
        from ai_lamp.vision.camera import Camera, CameraError

        photo = os.path.join(_REPO_ROOT, "outputs", "photos", "posture.jpg")
        try:
            Camera().capture(photo)
        except CameraError as exc:
            print(f"拍照失败：{exc}")
            return 1
    print(f"照片：{photo}")

    # 2) 发给豆包多模态判断坐姿
    # 坐姿是"粗活"（驼背/低头/太近），用小模型(flash)又快又省，不必上贵的 pro。
    # 复用 .env 里的 ARK_GRADER_MODEL；没配则回退默认 ARK_MODEL。
    from ai_lamp.env import load_env
    load_env()
    posture_model = os.environ.get("ARK_GRADER_MODEL") or None
    try:
        client = DoubaoClient(model=posture_model)
    except DoubaoConfigError as exc:
        print(f"配置错误：{exc}")
        return 2
    print(f"坐姿模型：{client.model}")

    t0 = time.time()
    reply = client.ask("请判断这张照片里孩子的坐姿。", image_path=photo,
                       system=POSTURE_SYSTEM, temperature=0.2)
    dt = time.time() - t0

    result = _parse_reply(reply)
    ok = result.get("posture_ok")
    issues = result.get("issues") or []
    advice = result.get("advice") or ""

    status = "✅ 坐姿良好" if ok else ("⚠️ 需要提醒" if ok is False else "（未能判定）")
    print(f"{status}  用时 {dt:.2f}s")
    if issues:
        print("问题：" + "、".join(issues))
    print("提醒：" + advice)

    # 3) 可选：把提醒说出来
    if args.speak and advice:
        from ai_lamp.voice.tts_client import TtsClient, TtsError

        spoken = os.path.join(_REPO_ROOT, "outputs", "audio", "posture_tip.mp3")
        try:
            TtsClient().synthesize(advice, spoken)
            print(f"语音：{spoken}（树莓派上 mpg123 播放）")
        except TtsError as exc:
            print(f"（TTS 合成失败，跳过播报：{exc}）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
