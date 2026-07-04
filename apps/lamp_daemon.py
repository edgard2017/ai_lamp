#!/usr/bin/env python3
"""台灯后台守护进程（lamp daemon）：豆包引导 + TTS 合成，常驻后台。

设计（分层）：
  输入源 → 豆包(引导式,多轮记忆) → TTS 合成音频 → (以后)扬声器播放
  现阶段输入源是一个「命名管道 FIFO」，方便无麦克风时用文字测试：
      echo "妈妈这道题我不会" > ~/ai_lamp/runtime/ask.fifo
  下周麦克风到位后，把输入源从 FIFO 换成 ASR、输出加 aplay 播放即可，主循环不变。

只依赖 requests（豆包 + TTS 都走 HTTP），老 Python 3.7 / 树莓派可跑。
用 systemd 托管即可开机自启、崩溃自恢复（见 deploy/lamp.service）。

用法（前台调试）：
    python3 apps/lamp_daemon.py
    # 另开一个终端： echo "6加7我算成13了" > ~/ai_lamp/runtime/ask.fifo
"""

import os
import signal
import sys
import time
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.tutor.doubao_client import DoubaoClient, DoubaoConfigError  # noqa: E402
from ai_lamp.tutor.prompts import TUTOR_SYSTEM  # noqa: E402
from ai_lamp.voice.tts_client import TtsClient, TtsConfigError, TtsError  # noqa: E402

_RUNTIME_DIR = os.path.join(_REPO_ROOT, "runtime")
_FIFO_PATH = os.path.join(_RUNTIME_DIR, "ask.fifo")
_AUDIO_DIR = os.path.join(_REPO_ROOT, "outputs", "audio")

_running = True


def _log(msg: str) -> None:
    """打到 stdout，systemd 会收进 journal（journalctl -u lamp 可看）。"""
    ts = datetime.now().strftime("%H:%M:%S")
    print("[%s] %s" % (ts, msg), flush=True)


def _on_term(signum, frame) -> None:
    global _running
    _running = False
    _log("收到停止信号，准备退出…")


def _ensure_fifo() -> None:
    os.makedirs(_RUNTIME_DIR, exist_ok=True)
    if not os.path.exists(_FIFO_PATH):
        os.mkfifo(_FIFO_PATH)
    os.makedirs(_AUDIO_DIR, exist_ok=True)


def _try_play(path: str) -> None:
    """尽力播放（有扬声器 + 播放器才出声）；没有也不报错，只记日志。"""
    import shutil
    import subprocess

    player = None
    if path.endswith(".mp3") and shutil.which("mpg123"):
        player = ["mpg123", "-q", path]
    elif path.endswith((".wav", ".pcm")) and shutil.which("aplay"):
        player = ["aplay", "-q", path]
    if player is None:
        return
    try:
        subprocess.run(player, timeout=30, check=False)
    except Exception as exc:  # noqa: BLE001 - 播放失败不影响主流程
        _log("播放跳过：%s" % exc)


def main() -> int:
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)

    try:
        tutor = DoubaoClient()
    except DoubaoConfigError as exc:
        _log("豆包配置错误：%s" % exc)
        return 2

    # TTS 可选：没配好也能只跑豆包（回复打日志，不合成音频）
    tts = None
    try:
        tts = TtsClient()
    except TtsConfigError as exc:
        _log("TTS 未配置（只跑豆包，不合成音频）：%s" % exc)

    _ensure_fifo()
    _log("台灯守护进程已启动 ✓  模型=%s" % tutor.model)
    _log("等待输入：echo \"孩子说的话\" > %s" % _FIFO_PATH)

    messages = [{"role": "system", "content": TUTOR_SYSTEM}]
    turn = 0

    while _running:
        # 打开 FIFO 会阻塞，直到有写入方；写入方关闭后循环重开（标准用法）
        try:
            with open(_FIFO_PATH, "r") as fifo:
                for raw in fifo:
                    text = raw.strip()
                    if not text:
                        continue
                    if text in ("quit", "exit", "退出", "结束"):
                        _log("收到退出指令。")
                        return 0

                    turn += 1
                    _log("孩子说: %s" % text)
                    messages.append({"role": "user", "content": text})

                    t0 = time.time()
                    try:
                        reply = tutor.chat(messages)
                    except Exception as exc:  # noqa: BLE001
                        _log("豆包调用失败：%s" % exc)
                        messages.pop()  # 回滚这轮，避免脏历史
                        turn -= 1
                        continue
                    messages.append({"role": "assistant", "content": reply})
                    _log("台灯答(%.1fs): %s" % (time.time() - t0, reply))

                    if tts is not None:
                        out = os.path.join(_AUDIO_DIR, "reply_%03d.mp3" % turn)
                        try:
                            tts.synthesize(reply, out)
                            _log("已合成音频: %s" % out)
                            _try_play(out)
                        except TtsError as exc:
                            _log("TTS 合成失败：%s" % exc)
        except Exception as exc:  # noqa: BLE001 - FIFO 异常不该杀死守护进程
            if _running:
                _log("FIFO 读取异常，1s 后重试：%s" % exc)
                time.sleep(1)

    _log("已退出。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
