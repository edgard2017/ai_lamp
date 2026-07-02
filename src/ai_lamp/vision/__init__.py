"""视觉层（本地·常开·免费）。

设计要点：把*算法*（纯几何，标准库即可）和*IO*（摄像头 / MediaPipe / 屏幕）分开。
- posture_rules : 关键点 → 特征 → 判定（无第三方依赖，可单测）
- monitor       : 防唠叨节流（无第三方依赖，可单测）
- calibration   : 个性化基准的采集与存取（无第三方依赖）
- pose_estimator: MediaPipe 封装，依赖懒加载（无摄像头的机器也能 import 本包）
"""

from .posture_rules import (
    Baseline,
    PostureConfig,
    PostureFeatures,
    PostureIssue,
    compute_features,
    judge,
)
from .monitor import PostureMonitor

__all__ = [
    "Baseline",
    "PostureConfig",
    "PostureFeatures",
    "PostureIssue",
    "compute_features",
    "judge",
    "PostureMonitor",
]
