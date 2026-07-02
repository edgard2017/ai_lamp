"""坐姿几何与判定 —— 纯逻辑，零第三方依赖。

没有摄像头、没有 MediaPipe，只用标准库。这样*算法*可以在任何机器（包括没有
摄像头的开发服务器 / CI）上做单测，并和 IO（摄像头 / 模型 / 屏幕）干净地分离。

坐标约定（与 MediaPipe 一致）：归一化图像坐标，x 向右、y **向下**，均在 [0, 1]。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]

# 本模块需要的关键点（MediaPipe Pose 33 点的子集）。
REQUIRED_LANDMARKS: Tuple[str, ...] = (
    "nose",
    "left_shoulder",
    "right_shoulder",
)


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _midpoint(a: Point, b: Point) -> Point:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


@dataclass(frozen=True)
class PostureFeatures:
    """从关键点导出的坐姿特征。

    除 shoulder_width 外都用肩宽归一化，因此小朋友单纯坐远/坐近时几乎不变；
    而 shoulder_width 本身刻意保留绝对尺度——它的增大正是「凑近」信号。
    """

    shoulder_width: float  # 原始肩宽（归一化图像单位）——凑近的代理量
    neck_vertical: float   # (肩中点_y - 鼻_y) / shoulder_width；低头时变小
    shoulder_tilt: float   # (右肩_y - 左肩_y) / shoulder_width；带符号


def compute_features(kp: Dict[str, Point]) -> Optional[PostureFeatures]:
    """关键点字典 → 特征；缺关键点或肩宽退化时返回 None。"""
    for name in REQUIRED_LANDMARKS:
        if name not in kp:
            return None

    left_shoulder = kp["left_shoulder"]
    right_shoulder = kp["right_shoulder"]
    nose = kp["nose"]

    shoulder_width = _dist(left_shoulder, right_shoulder)
    if shoulder_width < 1e-6:
        return None

    shoulder_mid = _midpoint(left_shoulder, right_shoulder)
    neck_vertical = (shoulder_mid[1] - nose[1]) / shoulder_width
    shoulder_tilt = (right_shoulder[1] - left_shoulder[1]) / shoulder_width

    return PostureFeatures(
        shoulder_width=shoulder_width,
        neck_vertical=neck_vertical,
        shoulder_tilt=shoulder_tilt,
    )


@dataclass(frozen=True)
class Baseline:
    """这孩子「坐端正」时的个性化基准。所有判定相对它，不用绝对角度。"""

    shoulder_width: float
    neck_vertical: float
    shoulder_tilt: float

    @classmethod
    def from_features(cls, feats: List[PostureFeatures]) -> "Baseline":
        n = len(feats)
        if n == 0:
            raise ValueError("需要至少一帧 PostureFeatures 才能建立基准")
        return cls(
            shoulder_width=sum(f.shoulder_width for f in feats) / n,
            neck_vertical=sum(f.neck_vertical for f in feats) / n,
            shoulder_tilt=sum(f.shoulder_tilt for f in feats) / n,
        )

    def to_dict(self) -> dict:
        return {
            "shoulder_width": self.shoulder_width,
            "neck_vertical": self.neck_vertical,
            "shoulder_tilt": self.shoulder_tilt,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Baseline":
        return cls(
            shoulder_width=float(d["shoulder_width"]),
            neck_vertical=float(d["neck_vertical"]),
            shoulder_tilt=float(d["shoulder_tilt"]),
        )


@dataclass(frozen=True)
class PostureConfig:
    """判定阈值（默认值与 config/posture.yaml 对应）。"""

    proximity_ratio: float = 1.20      # 肩宽/基准 超过即「太近」
    head_drop_ratio: float = 0.75      # neck_vertical 跌到基准该倍数以下即「低头」
    shoulder_tilt_delta: float = 0.12  # |肩斜-基准| 超过即「歪斜」

    @classmethod
    def from_dict(cls, d: dict) -> "PostureConfig":
        base = cls()
        return cls(
            proximity_ratio=float(d.get("proximity_ratio", base.proximity_ratio)),
            head_drop_ratio=float(d.get("head_drop_ratio", base.head_drop_ratio)),
            shoulder_tilt_delta=float(
                d.get("shoulder_tilt_delta", base.shoulder_tilt_delta)
            ),
        )


@dataclass(frozen=True)
class PostureIssue:
    """一个被检出的坐姿问题。severity ∈ [0,1]，表示超过阈值的程度。"""

    code: str       # "too_close" | "head_down" | "leaning"
    message: str    # 给小朋友的温柔提醒（建立信心，不打击）
    severity: float


def judge(
    features: PostureFeatures,
    baseline: Baseline,
    cfg: PostureConfig = PostureConfig(),
) -> List[PostureIssue]:
    """对单帧特征做判定，返回当前所有问题（可能为空）。

    纯函数、无状态：是否真的「提醒」交给 PostureMonitor 做时间上的节流。
    """
    issues: List[PostureIssue] = []

    # 1) 离得太近 / 趴太低（肩宽相对基准变大）
    if baseline.shoulder_width > 1e-6:
        ratio = features.shoulder_width / baseline.shoulder_width
        if ratio > cfg.proximity_ratio:
            severity = _clamp01((ratio - cfg.proximity_ratio) / cfg.proximity_ratio)
            issues.append(
                PostureIssue("too_close", "离得有点近啦，往后坐一点点会更护眼哦～", severity)
            )

    # 2) 低头（鼻子相对肩膀下沉，neck_vertical 变小）
    if baseline.neck_vertical > 1e-6:
        threshold = baseline.neck_vertical * cfg.head_drop_ratio
        if features.neck_vertical < threshold:
            severity = _clamp01((threshold - features.neck_vertical) / threshold)
            issues.append(
                PostureIssue("head_down", "头抬高一点点，坐直了写字更舒服～", severity)
            )

    # 3) 身体歪斜（肩斜偏离基准）
    delta = abs(features.shoulder_tilt - baseline.shoulder_tilt)
    if delta > cfg.shoulder_tilt_delta:
        severity = _clamp01((delta - cfg.shoulder_tilt_delta) / cfg.shoulder_tilt_delta)
        issues.append(
            PostureIssue("leaning", "身体好像歪啦，两边肩膀放平一些会更棒～", severity)
        )

    return issues
