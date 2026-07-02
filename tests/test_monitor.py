"""节流器 PostureMonitor 的单测。用注入的假时钟，无需真实等待。

直接跑：  python3 tests/test_monitor.py
也兼容：  pytest tests/test_monitor.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from ai_lamp.vision.monitor import PostureMonitor  # noqa: E402
from ai_lamp.vision.posture_rules import PostureIssue  # noqa: E402

ISSUE = PostureIssue("head_down", "抬头～", 0.5)


def codes(alerts):
    return [a.code for a in alerts]


def test_no_alert_before_persistence():
    mon = PostureMonitor(persistence_s=3.0, cooldown_s=30.0)
    assert mon.update([ISSUE], now=0.0) == []   # 刚出现
    assert mon.update([ISSUE], now=2.9) == []   # 还没满 3s


def test_alert_after_persistence():
    mon = PostureMonitor(persistence_s=3.0, cooldown_s=30.0)
    mon.update([ISSUE], now=0.0)
    assert codes(mon.update([ISSUE], now=3.0)) == ["head_down"]


def test_cooldown_blocks_repeat():
    mon = PostureMonitor(persistence_s=3.0, cooldown_s=30.0)
    mon.update([ISSUE], now=0.0)
    assert codes(mon.update([ISSUE], now=3.0)) == ["head_down"]  # 首次提醒
    assert mon.update([ISSUE], now=10.0) == []                   # 冷却内不重复
    assert codes(mon.update([ISSUE], now=33.1)) == ["head_down"]  # 冷却后再次


def test_interruption_resets_persistence():
    mon = PostureMonitor(persistence_s=3.0, cooldown_s=30.0)
    mon.update([ISSUE], now=0.0)
    mon.update([], now=1.0)          # 问题消失，连续计时清零
    assert mon.update([ISSUE], now=3.5) == []   # 从 t=3.5 重新计时
    assert mon.update([ISSUE], now=6.0) == []   # 距 3.5 才 2.5s，未满 3s
    assert codes(mon.update([ISSUE], now=6.5)) == ["head_down"]  # 满 3s 才提醒


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"  ok  {t.__name__}")
    print(f"\n{len(tests)} passed")


if __name__ == "__main__":
    _run_all()
