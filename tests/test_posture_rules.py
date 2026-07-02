"""坐姿几何 + 判定的单测。无需摄像头 / MediaPipe / pytest。

直接跑：  python3 tests/test_posture_rules.py
也兼容：  pytest tests/test_posture_rules.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from ai_lamp.vision.posture_rules import (  # noqa: E402
    Baseline,
    PostureConfig,
    compute_features,
    judge,
)

CFG = PostureConfig()


def make_kp(nose, left_shoulder, right_shoulder):
    return {
        "nose": nose,
        "left_shoulder": left_shoulder,
        "right_shoulder": right_shoulder,
    }


def scale_about(kp, center, factor):
    """把所有点绕 center 缩放 factor 倍——模拟整个人靠近摄像头（均匀放大）。"""
    cx, cy = center
    return {
        name: (cx + (x - cx) * factor, cy + (y - cy) * factor)
        for name, (x, y) in kp.items()
    }


# 端坐基准：肩在 y=0.6，肩宽 0.2；鼻在上方 (0.5, 0.35)
UPRIGHT = make_kp(nose=(0.5, 0.35), left_shoulder=(0.4, 0.6), right_shoulder=(0.6, 0.6))


def _baseline():
    feats = compute_features(UPRIGHT)
    assert feats is not None
    return Baseline.from_features([feats]), feats


def test_compute_features_basic():
    feats = compute_features(UPRIGHT)
    assert feats is not None
    assert abs(feats.shoulder_width - 0.2) < 1e-9
    # neck_vertical = (0.6 - 0.35) / 0.2 = 1.25
    assert abs(feats.neck_vertical - 1.25) < 1e-9
    assert abs(feats.shoulder_tilt - 0.0) < 1e-9


def test_missing_landmark_returns_none():
    assert compute_features({"nose": (0.5, 0.3)}) is None


def test_degenerate_shoulder_width_returns_none():
    kp = make_kp((0.5, 0.3), (0.5, 0.6), (0.5, 0.6))  # 两肩重合
    assert compute_features(kp) is None


def test_upright_has_no_issues():
    baseline, feats = _baseline()
    assert judge(feats, baseline, CFG) == []


def test_head_down_detected():
    baseline, _ = _baseline()
    # 鼻子下沉到 0.55 → neck_vertical=(0.6-0.55)/0.2=0.25 << 1.25*0.75
    feats = compute_features(make_kp((0.5, 0.55), (0.4, 0.6), (0.6, 0.6)))
    codes = {i.code for i in judge(feats, baseline, CFG)}
    assert "head_down" in codes
    assert "too_close" not in codes
    assert "leaning" not in codes


def test_too_close_detected_isolated():
    baseline, _ = _baseline()
    # 绕肩中点均匀放大 1.5 倍：肩宽涨 50%，但比值类特征不变 → 只应触发 too_close
    closer = scale_about(UPRIGHT, center=(0.5, 0.6), factor=1.5)
    feats = compute_features(closer)
    codes = {i.code for i in judge(feats, baseline, CFG)}
    assert codes == {"too_close"}


def test_leaning_detected():
    baseline, _ = _baseline()
    # 右肩压低：左(0.4,0.58) 右(0.6,0.66)
    feats = compute_features(make_kp((0.5, 0.35), (0.4, 0.58), (0.6, 0.66)))
    codes = {i.code for i in judge(feats, baseline, CFG)}
    assert "leaning" in codes


def test_severity_in_range():
    baseline, _ = _baseline()
    feats = compute_features(make_kp((0.5, 0.56), (0.4, 0.6), (0.6, 0.6)))
    for issue in judge(feats, baseline, CFG):
        assert 0.0 <= issue.severity <= 1.0


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
