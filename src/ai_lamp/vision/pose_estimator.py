"""MediaPipe Pose 封装：BGR 帧 → {关键点名: (x, y)} 字典。

MediaPipe / OpenCV 都**懒加载**，所以没装它们的机器（如开发服务器 / CI 跑几何单测）
依然能 import 本包。只有真正实例化 PoseEstimator 时才需要这些依赖。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

Point = Tuple[float, float]

# 关心的 MediaPipe Pose 关键点 -> 索引。
_LM_INDEX: Dict[str, int] = {
    "nose": 0,
    "left_eye": 2,
    "right_eye": 5,
    "left_ear": 7,
    "right_ear": 8,
    "left_shoulder": 11,
    "right_shoulder": 12,
}


@dataclass
class PoseResult:
    keypoints: Dict[str, Point]  # 过滤可见度后的 {名称: (x, y)}
    raw: object = None           # MediaPipe landmarks，供画骨架用（可能为 None）


class PoseEstimator:
    """把一帧图像转成关键点字典。"""

    def __init__(
        self,
        min_visibility: float = 0.5,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        import mediapipe as mp  # 懒加载

        self._mp = mp
        self.min_visibility = min_visibility
        self._pose = mp.solutions.pose.Pose(
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process(self, frame_bgr) -> PoseResult:
        import cv2  # 懒加载

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)

        keypoints: Dict[str, Point] = {}
        if not result.pose_landmarks:
            return PoseResult(keypoints=keypoints, raw=None)

        landmarks = result.pose_landmarks.landmark
        for name, idx in _LM_INDEX.items():
            lm = landmarks[idx]
            if getattr(lm, "visibility", 1.0) >= self.min_visibility:
                keypoints[name] = (lm.x, lm.y)

        return PoseResult(keypoints=keypoints, raw=result.pose_landmarks)

    def draw(self, frame_bgr, raw) -> None:
        """把骨架画到帧上（原地修改）。raw 为 None 时不做事。"""
        if raw is None:
            return
        mp = self._mp
        mp.solutions.drawing_utils.draw_landmarks(
            frame_bgr, raw, mp.solutions.pose.POSE_CONNECTIONS
        )

    def close(self) -> None:
        self._pose.close()

    def __enter__(self) -> "PoseEstimator":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
