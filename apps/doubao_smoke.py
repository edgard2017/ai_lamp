#!/usr/bin/env python3
"""豆包连通性冒烟测试：发一句话，看能不能拿到回复。

先在终端设置好（key 别贴进聊天/代码）：
    export ARK_API_KEY=你的火山引擎key
    export ARK_MODEL=ep-你的接入点id      # 文本接入点即可
然后：
    python3 apps/doubao_smoke.py
"""

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.tutor.doubao_client import DoubaoClient, DoubaoConfigError  # noqa: E402


def main() -> int:
    try:
        client = DoubaoClient()
    except DoubaoConfigError as exc:
        print(f"[配置缺失] {exc}", file=sys.stderr)
        return 2

    prompt = "用一句温柔的话鼓励一个刚把数学题做错、有点沮丧的小学一年级小朋友。"
    print(f"→ 提问：{prompt}")
    try:
        reply = client.ask(
            prompt,
            system="你是一位耐心、循循善诱的小学辅导老师，从不直接给答案，善于建立孩子的信心。",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[调用失败] {exc}", file=sys.stderr)
        return 1

    print(f"← 豆包：{reply}")
    print("\n✅ 连通成功")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
