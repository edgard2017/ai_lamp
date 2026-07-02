#!/usr/bin/env python3
"""多轮辅导对话：像聊天一样陪孩子做作业，豆包会记得前面聊过什么。

用法：
    # 纯文字多轮
    python3 apps/doubao_tutor.py
    # 用一张作业照片开场（灯头摄像头以后就是拍这张图）
    python3 apps/doubao_tutor.py data/samples/你的作业.jpeg

聊天中：
    - 直接打字回答，回车发送（你现在扮演小朋友）。
    - 输入 q / quit / exit 或按 Ctrl-C 结束。

原理：模型无状态，"记忆"靠本脚本维护的 messages 列表——每轮把你说的和豆包答的
依次 append 进去，再整份发过去。图片只在开场那条消息里带一次。
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.tutor.doubao_client import (  # noqa: E402
    DoubaoClient,
    DoubaoConfigError,
    user_message,
)
from ai_lamp.tutor.prompts import TUTOR_SYSTEM  # noqa: E402

_QUIT = {"q", "quit", "exit", "退出", "结束"}


def main() -> int:
    image_path = None
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        if not os.path.isfile(image_path):
            print(f"[找不到图片] {image_path}", file=sys.stderr)
            return 2

    try:
        client = DoubaoClient()
    except DoubaoConfigError as exc:
        print(f"[配置缺失] {exc}", file=sys.stderr)
        return 2

    # 历史缓冲：第一条是人设(system)，之后一问一答依次累加
    messages = [{"role": "system", "content": TUTOR_SYSTEM}]

    # 开场：有图就带图，让豆包先看题、挑第一道、问第一个小问题
    opening = "看看图里的作业，先挑一道题，引导我一步步想，别直接给答案。" if image_path \
        else "我要开始做作业啦，先陪我做第一道题吧。"
    messages.append(user_message(opening, image_path))

    print("=" * 56)
    print("多轮辅导已开始（输入 q 退出）。你现在扮演小朋友～")
    if image_path:
        print(f"开场图片：{image_path}")
    print("=" * 56)

    try:
        reply = client.chat(messages)
    except Exception as exc:  # noqa: BLE001
        print(f"[调用失败] {exc}", file=sys.stderr)
        return 1
    messages.append({"role": "assistant", "content": reply})
    print(f"\n老师：{reply}\n")

    while True:
        try:
            said = input("你（小朋友）：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见啦，明天继续加油！")
            break
        if not said:
            continue
        if said.lower() in _QUIT:
            print("再见啦，明天继续加油！")
            break

        messages.append({"role": "user", "content": said})
        try:
            reply = client.chat(messages)
        except Exception as exc:  # noqa: BLE001
            print(f"[调用失败] {exc}", file=sys.stderr)
            # 把这轮没答上的用户消息回退，避免历史里留一条没有回应的悬空消息
            messages.pop()
            continue
        messages.append({"role": "assistant", "content": reply})
        print(f"\n老师：{reply}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
