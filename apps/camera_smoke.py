#!/usr/bin/env python3
"""摄像头冒烟测试：拍一张照片，验证「台灯能睁眼看东西」。

只测硬件是否通，**不联网、不调云端**。下周把 OV5647 排线插到 Pi 上后，
在树莓派上跑这个脚本，能生成一张 jpg 就说明摄像头 OK。

用法（在树莓派上）：
    python3 apps/camera_smoke.py                 # 默认 1280x720
    python3 apps/camera_smoke.py 640 480         # 指定分辨率

输出到 outputs/photos/snap.jpg。开发机（无摄像头）上跑会明确报错提示，属正常。
"""

import os
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.vision.camera import Camera, CameraError  # noqa: E402


def main() -> int:
    width = int(sys.argv[1]) if len(sys.argv) > 1 else 1280
    height = int(sys.argv[2]) if len(sys.argv) > 2 else 720

    try:
        cam = Camera(width=width, height=height)
    except CameraError as exc:
        print(f"摄像头不可用：{exc}")
        return 2

    out_path = os.path.join(_REPO_ROOT, "outputs", "photos", "snap.jpg")
    print(f"用命令 {cam._bin}  分辨率 {width}x{height}  拍照中…")

    t0 = time.time()
    try:
        path = cam.capture(out_path)
    except CameraError as exc:
        print(f"拍照失败：{exc}")
        return 1
    dt = time.time() - t0

    size = os.path.getsize(path)
    print(f"✓ 成功  {size/1024:.1f} KB  用时 {dt:.2f}s")
    print(f"照片：{path}")
    print("查看：开发机可下载查看；或 scp 回来看画面是否正、够亮。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
