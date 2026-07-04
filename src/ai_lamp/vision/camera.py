"""树莓派 CSI 摄像头（OV5647 / Camera Module）静态拍照封装。零第三方依赖。

只用标准库 subprocess 调系统自带的拍照命令，**不依赖 picamera / cv2 / numpy**，
所以在老 Python 3.7、老 Raspbian buster 的 Pi3 上也能直接用。

两种系统栈自动适配：
  - 旧版（Raspbian buster 及更早）：raspistill   —— OV5647 默认支持
  - 新版（Bullseye/Bookworm 起）  ：libcamera-still

首次使用前，需在树莓派上启用摄像头（只做一次）：
  1. sudo raspi-config → Interface Options → Camera → Enable（新系统是 Legacy Camera）
  2. 老系统确认 /boot/config.txt 里有：start_x=1  与  gpu_mem=128
  3. sudo reboot
  4. 命令行自测： raspistill -o test.jpg -t 1000   （能生成 test.jpg 即硬件 OK）

用法：
    from ai_lamp.vision.camera import Camera
    cam = Camera()
    path = cam.capture("outputs/photos/snap.jpg")   # 返回实际写入的路径
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import List, Optional


class CameraError(RuntimeError):
    """拍照失败（未启用 / 未接好 / 命令缺失）时抛出，附带排查提示。"""


# 优先旧版 raspistill（buster），找不到再退到新版 libcamera-still（Bullseye+）
_LEGACY_BIN = "raspistill"
_LIBCAMERA_BIN = "libcamera-still"


class Camera:
    """CSI 摄像头静态拍照器。每次 capture() 拍一张 JPEG 存到指定路径。"""

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        warmup_ms: int = 1500,
        quality: int = 85,
        rotation: int = 0,
    ) -> None:
        """
        width/height  分辨率。坐姿检测 1280x720 足够，越大越慢、传云端越费流量。
        warmup_ms     曝光/白平衡预热时间；太短照片会偏暗，1000~2000ms 较稳。
        quality       JPEG 质量 1~100。
        rotation      画面旋转角度 0/90/180/270，摄像头装反了可在这里纠正。
        """
        self.width = width
        self.height = height
        self.warmup_ms = warmup_ms
        self.quality = quality
        self.rotation = rotation
        self._bin = self._detect_binary()

    @staticmethod
    def _detect_binary() -> str:
        """探测系统里可用的拍照命令，都没有则报错并给出安装/启用提示。"""
        for name in (_LEGACY_BIN, _LIBCAMERA_BIN):
            if shutil.which(name):
                return name
        raise CameraError(
            "找不到拍照命令（raspistill 或 libcamera-still）。\n"
            "请确认：① 在树莓派上运行（不是开发服务器）；"
            "② 已用 sudo raspi-config 启用摄像头；③ 已 reboot。"
        )

    def _build_cmd(self, out_path: str) -> List[str]:
        """按当前使用的命令拼接参数（两种命令的参数名不一样）。"""
        if self._bin == _LEGACY_BIN:
            cmd = [
                _LEGACY_BIN,
                "-n",                       # 无预览窗口（无头运行必需）
                "-t", str(self.warmup_ms),  # 预热时间
                "-w", str(self.width),
                "-h", str(self.height),
                "-q", str(self.quality),
                "-o", out_path,
            ]
            if self.rotation:
                cmd += ["-rot", str(self.rotation)]
        else:  # libcamera-still
            cmd = [
                _LIBCAMERA_BIN,
                "-n",
                "-t", str(self.warmup_ms),
                "--width", str(self.width),
                "--height", str(self.height),
                "-q", str(self.quality),
                "-o", out_path,
            ]
            if self.rotation:
                cmd += ["--rotation", str(self.rotation)]
        return cmd

    def capture(self, out_path: str, timeout: float = 30.0) -> str:
        """拍一张照片写到 out_path，返回该路径。失败抛 CameraError。"""
        out_dir = os.path.dirname(os.path.abspath(out_path))
        os.makedirs(out_dir, exist_ok=True)

        cmd = self._build_cmd(out_path)
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CameraError(f"拍照命令无法执行：{exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CameraError(
                f"拍照超时（{timeout}s）。可能摄像头未接好或被其它程序占用。"
            ) from exc

        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", "ignore").strip()
            raise CameraError(
                f"拍照失败（命令 {self._bin} 返回 {proc.returncode}）：{err[:300]}\n"
                "排查：摄像头排线是否插反/未插到底、raspi-config 是否已启用、是否已 reboot。"
            )

        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise CameraError("命令返回成功但没生成有效图片，请检查摄像头连接。")

        return out_path
