#!/usr/bin/env python3
"""豆包「看图」冒烟测试：喂一张作业照片，看模型能不能读懂并循循善诱地引导。

用法：
    python3 apps/doubao_image_smoke.py 路径/到/作业照片.jpg
    python3 apps/doubao_image_smoke.py 路径/到/照片.jpg "这道题我不会，帮我看看"

说明：
  - 第 1 个参数：图片路径（jpg/png 都行）。
  - 第 2 个参数（可选）：想对豆包说的话，默认是"看看图里这道题，引导我一步步想"。
  - key/模型从 .env 自动读（ARK_MODEL 需为多模态接入点，如 doubao-seed-2-1-pro）。
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.tutor.doubao_client import DoubaoClient, DoubaoConfigError  # noqa: E402
from ai_lamp.tutor.prompts import TUTOR_SYSTEM  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python3 apps/doubao_image_smoke.py <图片路径> [想说的话]", file=sys.stderr)
        return 2

    image_path = sys.argv[1]
    if not os.path.isfile(image_path):
        print(f"[找不到图片] {image_path}", file=sys.stderr)
        return 2

    text = sys.argv[2] if len(sys.argv) > 2 else "看看图里这道题，先告诉我题目是什么，再引导我一步步想，别直接给答案。"

    try:
        client = DoubaoClient()
    except DoubaoConfigError as exc:
        print(f"[配置缺失] {exc}", file=sys.stderr)
        return 2

    print(f"→ 图片：{image_path}")
    print(f"→ 提问：{text}")
    try:
        reply = client.ask(text, image_path=image_path, system=TUTOR_SYSTEM)
    except Exception as exc:  # noqa: BLE001
        print(f"[调用失败] {exc}", file=sys.stderr)
        return 1

    print(f"← 豆包：{reply}")
    print("\n✅ 看图成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
