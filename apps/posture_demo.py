#!/usr/bin/env python3
"""实时坐姿 demo：摄像头 → 骨架 → 坐姿判定 → 屏幕/控制台反馈。

需要摄像头的机器（如树莓派），并已 `pip install -r requirements.txt`。

键位：
  c  标定（坐端正后采集若干帧，作为这孩子的个性化基准）
  r  清除基准
  q  退出

说明：OpenCV 的 putText 不支持中文，画面上用 ASCII 状态标签，温柔的中文提醒打到
控制台。正式 UI 再用 PIL/Qt 绘制中文。
"""

from __future__ import annotations

import os
import sys
import time

# 让脚本无需安装就能 import 到 src/ 下的 ai_lamp 包
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from ai_lamp.vision.calibration import (  # noqa: E402
    BaselineCollector,
    load_baseline,
    save_baseline,
)
from ai_lamp.vision.monitor import PostureMonitor  # noqa: E402
from ai_lamp.vision.posture_rules import (  # noqa: E402
    PostureConfig,
    compute_features,
    judge,
)

_BASELINE_PATH = os.path.join(_REPO_ROOT, "data", "calibration", "baseline.json")
_CONFIG_PATH = os.path.join(_REPO_ROOT, "config", "posture.yaml")

# 画面上用的 ASCII 状态标签（中文提醒走 PostureIssue.message → 控制台）
_CODE_LABEL = {
    "too_close": "TOO CLOSE",
    "head_down": "HEAD DOWN",
    "leaning": "LEANING",
}


def _load_config():
    """读取 config/posture.yaml；缺 PyYAML 或文件则用默认值。"""
    defaults = dict(
        judgment={},
        estimator=dict(min_visibility=0.5, model_complexity=1),
        monitor=dict(persistence_s=3.0, cooldown_s=30.0),
        calibration=dict(frames=30),
    )
    try:
        import yaml

        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        for key, val in loaded.items():
            defaults[key] = {**defaults.get(key, {}), **(val or {})}
    except Exception as exc:  # noqa: BLE001 - demo 容错，用默认值即可
        print(f"[config] 用默认参数（{exc}）")
    return defaults


def main() -> int:
    try:
        import cv2
    except ImportError:
        print("需要 opencv-python：pip install -r requirements.txt", file=sys.stderr)
        return 1
    try:
        from ai_lamp.vision.pose_estimator import PoseEstimator
    except ImportError:
        print("需要 mediapipe：pip install -r requirements.txt", file=sys.stderr)
        return 1

    cfg_all = _load_config()
    cfg = PostureConfig.from_dict(cfg_all.get("judgment", {}))
    est_cfg = cfg_all.get("estimator", {})
    mon_cfg = cfg_all.get("monitor", {})
    calib_frames = int(cfg_all.get("calibration", {}).get("frames", 30))

    estimator = PoseEstimator(
        min_visibility=float(est_cfg.get("min_visibility", 0.5)),
        model_complexity=int(est_cfg.get("model_complexity", 1)),
    )
    monitor = PostureMonitor(
        persistence_s=float(mon_cfg.get("persistence_s", 3.0)),
        cooldown_s=float(mon_cfg.get("cooldown_s", 30.0)),
    )

    baseline = load_baseline(_BASELINE_PATH)
    if baseline is not None:
        print(f"[baseline] 已加载：{_BASELINE_PATH}")
    else:
        print("[baseline] 暂无基准，按 c 标定（让小朋友坐端正）")

    collector: BaselineCollector | None = None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("打不开摄像头（/dev/video0）", file=sys.stderr)
        return 1

    print("运行中：c=标定  r=清除基准  q=退出")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame = cv2.flip(frame, 1)  # 镜像，更符合直觉

            result = estimator.process(frame)
            estimator.draw(frame, result.raw)
            features = compute_features(result.keypoints)

            # 标定中：累计帧
            if collector is not None and features is not None:
                collector.add(features)
                cv2.putText(
                    frame,
                    f"CALIBRATING {collector.count}/{calib_frames}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 200, 255),
                    2,
                )
                if collector.count >= calib_frames:
                    baseline = collector.build()
                    save_baseline(baseline, _BASELINE_PATH)
                    collector = None
                    monitor.reset()
                    print(f"[baseline] 标定完成并保存：{_BASELINE_PATH}")

            # 正常监测
            elif baseline is not None and features is not None:
                issues = judge(features, baseline, cfg)
                # 画面上显示当前检出（未经节流）
                y = 30
                for issue in issues:
                    cv2.putText(
                        frame,
                        _CODE_LABEL.get(issue.code, issue.code),
                        (10, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2,
                    )
                    y += 28
                # 经过持续+冷却节流后，才真正"提醒"
                for alert in monitor.update(issues, time.monotonic()):
                    print(f"🔔 {alert.message}  (severity={alert.severity:.2f})")

            elif baseline is None:
                cv2.putText(
                    frame,
                    "press 'c' to calibrate",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 200, 255),
                    2,
                )

            cv2.imshow("AI Lamp - posture", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("c"):
                collector = BaselineCollector()
                print("[baseline] 开始标定，请坐端正……")
            elif key == ord("r"):
                baseline = None
                monitor.reset()
                if os.path.exists(_BASELINE_PATH):
                    os.remove(_BASELINE_PATH)
                print("[baseline] 已清除")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        estimator.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
