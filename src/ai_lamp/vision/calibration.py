"""个性化基准的采集与存取。零第三方依赖。

整个坐姿判定都*相对于这个基准*，而不是绝对角度——所以换机位、换小孩，只需
重新标定 10 秒（「坐端正一下」），不用改任何代码。
"""

from __future__ import annotations

import json
import os
from typing import List, Optional

from .posture_rules import Baseline, PostureFeatures


class BaselineCollector:
    """在一小段时间窗内累计特征，再平均成一个 Baseline。"""

    def __init__(self) -> None:
        self._feats: List[PostureFeatures] = []

    def add(self, feat: PostureFeatures) -> None:
        self._feats.append(feat)

    @property
    def count(self) -> int:
        return len(self._feats)

    def build(self) -> Baseline:
        """把已采集的特征平均成基准；未采到任何帧会抛 ValueError。"""
        return Baseline.from_features(self._feats)

    def reset(self) -> None:
        self._feats.clear()


def save_baseline(baseline: Baseline, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(baseline.to_dict(), f, ensure_ascii=False, indent=2)


def load_baseline(path: str) -> Optional[Baseline]:
    """从 JSON 读取基准；文件不存在或损坏返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Baseline.from_dict(json.load(f))
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None
